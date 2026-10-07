# -*- coding: utf-8 -*-
from odoo import _, models
from odoo.exceptions import UserError
from odoo.modules import module as odoo_module

BATCH = 1000


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def action_yr_delete_imported(self):
        """Paramètres › « Supprimer les clients et ventes importés » (fastmag): to import them again from scratch.
        Stores, sellers and articles are kept. A customer already used elsewhere (POS order, invoice…) is archived."""
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_('Réservé aux administrateurs.'))
        env = self.env(su=True)
        commit = not odoo_module.current_test and not self.env.registry.in_test_mode()
        counts = {'sales': 0, 'purchases': 0, 'customers': 0, 'archived': 0}
        for model, key in (('yr.legacy.sale.line', 'sales'), ('yr.legacy.purchase', 'purchases')):
            Model = env[model].with_context(active_test=False)
            while True:
                records = Model.search([], limit=10000)
                if not records:
                    break
                counts[key] += len(records)
                records.unlink()
                if commit:
                    self.env.cr.commit()
        Partner = env['res.partner'].with_context(active_test=False, yr_migration_force=True)
        done = Partner.browse()
        while True:
            partners = Partner.search([('yr_legacy_code', '!=', False), ('id', 'not in', done.ids)], limit=BATCH)
            if not partners:
                break
            try:
                with self.env.cr.savepoint():
                    partners.unlink()
                counts['customers'] += len(partners)
            except Exception:  # noqa: BLE001 - some are used elsewhere: one by one
                for partner in partners:
                    try:
                        with self.env.cr.savepoint():
                            partner.unlink()
                        counts['customers'] += 1
                    except Exception:  # noqa: BLE001 - kept, archived
                        partner.write({'active': False})
                        done |= partner
                        counts['archived'] += 1
            if commit:
                self.env.cr.commit()
        # the customer / sales files can be imported again (no « déjà importé » nor resume)
        env['yr.migration.log'].search([('file_type', 'in', ['client_new', 'client_old', 'client_ca',
                                                                'sales_detail'])]).unlink()
        return {'type': 'ir.actions.client', 'tag': 'display_notification', 'params': {
            'title': _('Données importées supprimées'), 'type': 'success', 'sticky': True,
            'message': _('%(sales)s lignes de ventes, %(purchases)s achats clients et %(customers)s clients '
                         'supprimés ; %(archived)s clients archivés (utilisés ailleurs).', **counts),
            'next': {'type': 'ir.actions.client', 'tag': 'reload'}}}
