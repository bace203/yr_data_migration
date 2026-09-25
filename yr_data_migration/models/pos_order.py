# -*- coding: utf-8 -*-
from odoo import fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    # user_id = the cashier (POS session); the seller may be another person
    yr_seller_id = fields.Many2one('res.users', 'Vendeur', index=True,
                                   help='Personne qui a conseillé / vendu, si différente du caissier.')
    yr_seller_code_legacy = fields.Char('Code vendeur (fastmag)')
