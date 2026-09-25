# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

FROZEN_FIELDS = ('yr_legacy_amount', 'yr_migration_date')


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Already in Fidélité & CRM and reused: birth_day / birth_month / birth_year, customer_code (= card number,
    # also the barcode scanned at the POS), crm_store_id, crm_first_order_date…
    yr_gender = fields.Selection([('f', 'Femme'), ('h', 'Homme')], 'Sexe')
    yr_legacy_code = fields.Char('Code client fastmag', index=True, copy=False,
                                 help='Numéro de carte / numéro client dans fastmag.')
    yr_legacy_old_code = fields.Char('Ancien code client (fastmag)', copy=False)
    yr_entry_date = fields.Date('Date d\'entrée (adhésion)')
    yr_first_purchase_legacy = fields.Date('Premier achat (fastmag)')
    yr_seller_code = fields.Char('Vendeuse (fastmag)')
    yr_legacy_segment = fields.Char('Segment fastmag', help='Ex. FID, OC, PA, MO')
    yr_npai = fields.Boolean('NPAI', help='N\'habite pas à l\'adresse indiquée (courrier revenu).')

    # purchases made before Odoo: frozen once set, visible to the « données de migration » group only
    yr_legacy_amount = fields.Monetary('Montant TTC à la migration', currency_field='yr_currency_id', readonly=True,
                                       copy=False, groups='yr_data_migration.group_migration_data')
    yr_migration_date = fields.Date('Date de migration', readonly=True, copy=False,
                                    groups='yr_data_migration.group_migration_data')
    yr_currency_id = fields.Many2one('res.currency', compute='_compute_yr_currency_id')

    # « chiffre d'affaires clients depuis 2 ans » file: purchase lines, counted by Fidélité & CRM
    yr_legacy_purchase_ids = fields.One2many('yr.legacy.purchase', 'partner_id', 'Achats fastmag')

    def _compute_yr_currency_id(self):
        for partner in self:
            partner.yr_currency_id = partner.company_id.currency_id or self.env.company.currency_id

    def write(self, vals):
        if any(f in vals for f in FROZEN_FIELDS) and not self.env.context.get('yr_migration_force'):
            for partner in self.sudo():
                for fname in FROZEN_FIELDS:
                    if fname in vals and partner[fname] and partner[fname] != vals[fname]:
                        raise UserError(_('Le montant et la date de migration sont figés une fois renseignés.'))
        return super().write(vals)
