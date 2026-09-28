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
