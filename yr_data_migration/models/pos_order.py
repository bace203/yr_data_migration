# -*- coding: utf-8 -*-
from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # user_id / employee_id = the cashier; the seller is the person who advised the customer, chosen before payment
    yr_seller_id = fields.Many2one('hr.employee', 'Vendeur', index=True,
                                   help='Personne qui a conseillé / vendu, choisie en caisse avant le paiement '
                                        '(peut être différente du caissier).')
    # sent by the POS: hr.employee is not always loaded in the POS, so the id travels as a plain number
    yr_seller_ref = fields.Integer('Vendeur (caisse)', copy=False)
    yr_seller_code_legacy = fields.Char('Code vendeur (fastmag)')

    @api.model
    def _yr_seller_vals(self, vals):
        if 'yr_seller_ref' in vals:
            employee = self.env['hr.employee'].sudo().browse(vals['yr_seller_ref'] or 0).exists()
            vals['yr_seller_id'] = employee.id or False
        elif 'yr_seller_id' in vals:      # changed in the back office: the POS copy follows
            vals['yr_seller_ref'] = vals['yr_seller_id'] or 0
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        return super().create([self._yr_seller_vals(dict(vals)) for vals in vals_list])

    def write(self, vals):
        return super().write(self._yr_seller_vals(dict(vals)))

    # tickets of the fastmag history (« Détail des ventes »): real orders of a closed « historique » session,
    # without payment, accounting entry nor stock move
    yr_fastmag_ticket = fields.Char('Ticket fastmag', index='btree_not_null', copy=False,
                                    help='Magasin fastmag / n° de vente du ticket importé.')
    yr_fastmag_card = fields.Char('Carte fidélité (fastmag)', copy=False)
    yr_seller_name = fields.Char('Vendeur (fastmag)', copy=False)
    yr_cashier_name = fields.Char('Caissier (fastmag)', copy=False)

    def init(self):
        super().init()
        # the CRM history (yr.legacy.purchase) skips the days already present as fastmag tickets
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS pos_order_yr_fastmag_card_date_idx
                ON pos_order (yr_fastmag_card, date_order) WHERE yr_fastmag_card IS NOT NULL
        """)


class PosOrderLine(models.Model):
    _inherit = 'pos.order.line'

    yr_fastmag_line_id = fields.Many2one('yr.legacy.sale.line', 'Ligne fastmag', index='btree_not_null',
                                         ondelete='set null', copy=False)


class PosSession(models.Model):
    _inherit = 'pos.session'

    yr_fastmag = fields.Boolean('Historique fastmag', copy=False, index=True,
                                help='Session fermée qui contient les tickets importés de fastmag.')
