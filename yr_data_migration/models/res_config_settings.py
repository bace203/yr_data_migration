# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.modules import module as odoo_module

BATCH = 1000
# what each « Supprimer » button removes (the files can then be imported again)
DELETE_KINDS = {
    'customers': ['customers'],
    'sales': ['pos_orders', 'sales'],
    'pos_orders': ['pos_orders'],
    'purchases': ['purchases'],
    'codes': ['codes'],
    'all': ['pos_orders', 'sales', 'purchases', 'customers', 'codes'],
}
LOG_TYPES = {
    'customers': ['client_new', 'client_old'], 'sales': ['sales_detail'], 'purchases': ['client_ca'],
    'codes': ['client_codes'],
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    yr_sales_without_order = fields.Integer('Lignes de ventes fastmag sans commande PdV',
                                            compute='_compute_yr_fastmag_counts')
    yr_fastmag_order_count = fields.Integer('Commandes PdV fastmag', compute='_compute_yr_fastmag_counts')

    @api.depends('company_id')                      # computed on the settings screen (new record) too
    def _compute_yr_fastmag_counts(self):
        cr = self.env.cr
        cr.execute('SELECT count(*) FROM yr_legacy_sale_line WHERE pos_order_id IS NULL')
        without = cr.fetchone()[0]
        cr.execute('SELECT count(*) FROM pos_order WHERE yr_fastmag_ticket IS NOT NULL')
        orders = cr.fetchone()[0]
        for settings in self:
            settings.yr_sales_without_order = without
            settings.yr_fastmag_order_count = orders

    def _yr_check_admin(self):
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Réservé aux administrateurs.'))

    def _yr_commit(self):
        if not odoo_module.current_test and not self.env.registry.in_test_mode():
            self.env.cr.commit()

    def _yr_delete(self, kind):
        """Deletes imported fastmag data of one kind; stores, sellers and articles are always kept.
        A customer already used elsewhere (Posify ticket, invoice…) is archived instead."""
        self._yr_check_admin()
        env = self.env(su=True)
        counts = dict.fromkeys(['pos_orders', 'sales', 'purchases', 'customers', 'archived', 'codes'], 0)
        parts = DELETE_KINDS[kind]
        if 'pos_orders' in parts:
            counts['pos_orders'] = env['yr.legacy.sale.line']._yr_delete_pos_orders()
        for part, model in (('sales', 'yr.legacy.sale.line'), ('purchases', 'yr.legacy.purchase'),
                            ('codes', 'yr.client.code')):
            if part not in parts:
                continue
            table = env[model]._table
            while True:
                self.env.cr.execute('DELETE FROM %s WHERE id IN (SELECT id FROM %s LIMIT 50000)' % (table, table))
                if not self.env.cr.rowcount:
                    break
                counts[part] += self.env.cr.rowcount
                self._yr_commit()
            env[model].invalidate_model()
        if 'customers' in parts:
            counts['customers'], counts['archived'] = self._yr_delete_customers(env, keep_history=kind != 'all')
        log_types = [t for part in parts for t in LOG_TYPES.get(part, [])]
        if kind == 'pos_orders':
            log_types = []
        # these files can be imported again (no « déjà importé » nor resume)
        env['yr.migration.log'].search([('file_type', 'in', log_types)]).unlink()
        messages = {
            'pos_orders': _('%s commandes PdV fastmag'), 'sales': _('%s lignes de ventes'),
            'purchases': _('%s achats clients (historique CA)'), 'customers': _('%s clients'),
            'codes': _('%s codes clients'),
        }
        message = ', '.join(messages[part] % counts[part] for part in parts) + _(' supprimé(s).')
        if counts['archived']:
            message += ' ' + _('%s client(s) archivé(s) (utilisés ailleurs).', counts['archived'])
        if kind == 'pos_orders':
            message += ' ' + _('Les lignes de ventes sont gardées : « Créer les commandes PdV » les refait.')
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Données fastmag supprimées'), 'type': 'success', 'sticky': True, 'message': message,
            'next': {'type': 'ir.actions.client', 'tag': 'reload'}}}

    def _yr_delete_customers(self, env, keep_history=True):
        if keep_history:
            # purchase history, sales lines and POS orders are kept: re-importing the customers links them again
            self.env.cr.execute("""
                UPDATE yr_legacy_purchase SET partner_id = NULL
                 WHERE partner_id IN (SELECT id FROM res_partner WHERE yr_legacy_code IS NOT NULL)
            """)
            env['yr.legacy.purchase'].invalidate_model(['partner_id'])
            self.env.cr.execute("""
                UPDATE pos_order SET partner_id = NULL
                 WHERE yr_fastmag_ticket IS NOT NULL
                   AND partner_id IN (SELECT id FROM res_partner WHERE yr_legacy_code IS NOT NULL)
            """)
            env['pos.order'].invalidate_model(['partner_id'])
        Partner = env['res.partner'].with_context(active_test=False, yr_migration_force=True)
        done, deleted, archived = Partner.browse(), 0, 0
        while True:
            partners = Partner.search([('yr_legacy_code', '!=', False), ('id', 'not in', done.ids)], limit=BATCH)
            if not partners:
                break
            try:
                with self.env.cr.savepoint():
                    partners.unlink()
                deleted += len(partners)
            except Exception:  # noqa: BLE001 - some are used elsewhere: one by one
                for partner in partners:
                    try:
                        with self.env.cr.savepoint():
                            partner.unlink()
                        deleted += 1
                    except Exception:  # noqa: BLE001 - kept, archived
                        partner.write({'active': False})
                        done |= partner
                        archived += 1
            self._yr_commit()
        return deleted, archived

    def action_yr_delete_imported(self):
        """Everything imported from fastmag (customers, sales, POS orders, history, codes)."""
        return self._yr_delete('all')

    def action_yr_delete_customers(self):
        return self._yr_delete('customers')

    def action_yr_delete_sales(self):
        return self._yr_delete('sales')

    def action_yr_delete_pos_orders(self):
        return self._yr_delete('pos_orders')

    def action_yr_delete_purchases(self):
        return self._yr_delete('purchases')

    def action_yr_delete_codes(self):
        return self._yr_delete('codes')

    def action_yr_make_pos_orders(self):
        """Attaches the lines to the stores / articles known now, then makes the missing POS orders in the
        background."""
        self._yr_check_admin()
        Line = self.env['yr.legacy.sale.line'].sudo()
        linked = Line._yr_link_stores_products()
        linked['employees'] = Line._link_employees()          # « Nom(s) fastmag » filled in since the import
        Line._yr_trigger_pos_orders()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Commandes du point de vente'), 'type': 'success', 'sticky': True,
            'message': _('%(stores)s ligne(s) rattachée(s) à leur magasin, %(products)s à leur article et '
                         '%(employees)s à leur vendeur / caissier. '
                         'Les commandes PdV manquantes sont créées en arrière-plan (Point de Vente › Commandes).',
                         **linked)}}
