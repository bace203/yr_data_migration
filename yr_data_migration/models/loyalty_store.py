# -*- coding: utf-8 -*-
from odoo import fields, models


class LoyaltyStore(models.Model):
    _inherit = 'loyalty.store'

    yr_fastmag_code = fields.Char('Code magasin fastmag', index=True,
                                  help='Code du magasin dans les fichiers fastmag (ex. YR_YOUG). '
                                       'Plusieurs codes : séparés par une virgule.')
