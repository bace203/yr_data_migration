# -*- coding: utf-8 -*-
from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Native fields used for the fastmag columns (no duplicates):
    #   réf article → default_code, EAN bar → barcode, Désignation → name, Prix → list_price, UN → uom_id,
    #   axe / sous axe → pos_categ_ids (POS categories axe › sous-axe), Fourn → seller_ids.
    # « bu » is deliberately not kept.
    yr_site = fields.Char('Site (fastmag)')
    yr_category_code = fields.Char('Catégorie (fastmag)', index=True, help='Ex. CAFV')
    yr_brand = fields.Char('Marque')
    yr_line = fields.Char('Ligne', help='Ex. CN3')
    yr_axe_id = fields.Many2one('pos.category', 'Axe', index=True, help='Catégorie PdV de l\'axe (ex. MAQUILLAGE).')
    yr_sub_axe_id = fields.Many2one('pos.category', 'Sous-axe', index=True,
                                    help='Sous-catégorie PdV (ex. TEINT), rangée sous l\'axe.')
    yr_nature = fields.Char('Nature')
    yr_packaging = fields.Char('Conditionnement')
    yr_gender = fields.Char('Genre')
    yr_status = fields.Char('Statut (fastmag)')
    yr_create_date_legacy = fields.Date('Créé dans fastmag le')
    yr_supplier_code = fields.Char('Code fournisseur (fastmag)')
