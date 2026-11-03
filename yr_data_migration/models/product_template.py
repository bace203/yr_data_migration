# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Native fields used for the fastmag columns (no duplicates):
    #   réf article → default_code, EAN bar → barcode, Désignation → name, Prix → list_price, UN → uom_id,
    #   axe / sous axe → pos_categ_ids (POS categories axe › sous-axe), Fourn → seller_ids.
    # « bu » is deliberately not kept.
    yr_site = fields.Char('Site')
    yr_category_code = fields.Char('Catégorie article', index=True, help='Ex. CAFV')
    yr_brand = fields.Char('Marque')
    yr_line = fields.Char('Ligne', help='Ex. CN3')
    yr_axe_id = fields.Many2one('pos.category', 'Axe', index=True, help='Catégorie PdV de l\'axe (ex. MAQUILLAGE).')
    yr_sub_axe_id = fields.Many2one('pos.category', 'Sous-axe', index=True,
                                    help='Sous-catégorie PdV (ex. TEINT), rangée sous l\'axe.')
    yr_nature = fields.Char('Nature')
    yr_packaging = fields.Char('Contenance / conditionnement')
    yr_gender = fields.Char('Genre')
    yr_status = fields.Char('Statut')
    yr_create_date_legacy = fields.Date('Date de création de l\'article')
    yr_supplier_code = fields.Char('Code fournisseur')
    # « Référence interne » (default_code) = the Sage X3 reference; the fastmag article code is kept apart
    yr_fastmag_code = fields.Char('Réf. fastmag', index=True, copy=False,
                                  help='Référence de l\'article dans fastmag (fichier articles fastmag, historique des '
                                       'ventes). La « Référence interne » est la référence Sage X3.')


class ProductProduct(models.Model):
    _inherit = 'product.product'

    yr_fastmag_code = fields.Char('Réf. fastmag', related='product_tmpl_id.yr_fastmag_code')

    @api.model
    def _load_pos_data_fields(self, config_id):
        fields_list = super()._load_pos_data_fields(config_id)
        return fields_list + ['yr_fastmag_code'] if fields_list else fields_list
