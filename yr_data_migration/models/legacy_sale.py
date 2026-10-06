# -*- coding: utf-8 -*-
"""fastmag sales detail (« Détail ventes » file): one line per ticket line, with the cashier (Utilisateur) and the
seller (Vendeur). The totals per customer, day and store also feed the purchase history (yr.legacy.purchase)."""
from odoo import _, api, fields, models
from odoo.tools import SQL


def name_key(value):
    return ' '.join(str(value or '').upper().split())


class YrLegacySaleLine(models.Model):
    _name = 'yr.legacy.sale.line'
    _description = 'Vente fastmag (détail)'
    _order = 'date desc, ticket desc, sequence, id'
    _rec_name = 'ticket'

    shop_code = fields.Char('Magasin fastmag', required=True, index=True)
    store_id = fields.Many2one('loyalty.store', 'Magasin', index=True)
    pos_config_id = fields.Many2one('pos.config', 'Point de vente', index=True,
                                    help='Caisse (point de vente) du magasin de la vente.')
    company_id = fields.Many2one('res.company', 'Société', required=True, default=lambda self: self.env.company)
    ticket = fields.Char('Ticket', required=True, index=True)
    sequence = fields.Integer('N° de ligne', default=1)
    date = fields.Date('Date', required=True, index=True)
    cashier_name = fields.Char('Utilisateur (caissier)', index=True)
    cashier_id = fields.Many2one('hr.employee', 'Caissier', index=True)
    seller_name = fields.Char('Vendeur fastmag', index=True)
    seller_id = fields.Many2one('hr.employee', 'Vendeur', index=True)
    card = fields.Char('Carte fidélité', index=True)
    legacy_client_id = fields.Char('N° client fastmag')
    partner_id = fields.Many2one('res.partner', 'Client', index=True)
    product_ref = fields.Char('Réf. article')
    barcode = fields.Char('Code-barres')
    product_id = fields.Many2one('product.product', 'Article', index=True)
    name = fields.Char('Désignation')
    axe = fields.Char('Axe')
    product_line = fields.Char('Ligne')
    is_stamp = fields.Boolean('Droit de timbre')
    qty = fields.Float('Quantité', digits='Product Unit of Measure')
    price_unit = fields.Float('Prix', digits='Product Price')
    discount = fields.Float('Remise (%)')
    amount = fields.Float('Total TTC', digits='Product Price')
    reason = fields.Char('Motif')
    comment = fields.Char('Commentaire')

    _sql_constraints = [('line_unique', 'unique(shop_code, ticket, sequence)',
                         'Une seule ligne par magasin, ticket et n° de ligne.')]

    @api.model
    def _link_partners(self, cards=None):
        self.flush_model()
        self.env['res.partner'].flush_model(['customer_code', 'yr_legacy_code'])
        where = SQL('l.card = ANY(%s)', list(cards)) if cards is not None else SQL('l.card IS NOT NULL')
        self.env.cr.execute(SQL("""
            UPDATE yr_legacy_sale_line l SET partner_id = p.id
              FROM res_partner p
             WHERE (p.customer_code = l.card OR p.yr_legacy_code = l.card)
               AND l.partner_id IS DISTINCT FROM p.id AND %s
        """, where))
        self.invalidate_model(['partner_id'])

    @api.model
    def _employee_index(self):
        """Upper-cased name / fastmag names → employee."""
        index = {}
        for employee in self.env['hr.employee'].sudo().with_context(active_test=False).search([]):
            for alias in (employee.yr_fastmag_name or '').split(','):
                if name_key(alias):
                    index[name_key(alias)] = employee
        for employee in self.env['hr.employee'].sudo().search([]):
            index.setdefault(name_key(employee.name), employee)
        return index

    @api.model
    def _link_employees(self):
        """Attach cashiers and sellers known by their fastmag name (after creating / renaming employees)."""
        index = self._employee_index()
        count = 0
        for field, name_field in (('seller_id', 'seller_name'), ('cashier_id', 'cashier_name')):
            groups = self._read_group([(field, '=', False), (name_field, '!=', False)], [name_field])
            for (name,) in groups:
                employee = index.get(name_key(name))
                if employee:
                    lines = self.search([(field, '=', False), (name_field, '=', name)])
                    lines.write({field: employee.id})
                    count += len(lines)
        return count

    def action_link_employees(self):
        count = self._link_employees()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success' if count else 'info', 'sticky': False,
                       'message': _('%s ligne(s) rattachée(s) à un employé.', count) if count else
                       _('Aucune nouvelle correspondance : renseignez le champ « Nom(s) fastmag » '
                                  'des employés.'),
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }
