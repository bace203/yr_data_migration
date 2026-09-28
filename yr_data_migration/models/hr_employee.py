# -*- coding: utf-8 -*-
from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    yr_fastmag_name = fields.Char(
        'Nom(s) fastmag', index=True,
        help='Nom du vendeur ou de l\'utilisateur dans les fichiers fastmag (ex. JBELI RYM, RIM), si différent. '
             'Plusieurs : séparés par une virgule. Sert à rattacher les ventes importées.')
