# -*- coding: utf-8 -*-
from odoo import _, fields, models
from odoo.exceptions import UserError

FROZEN_FIELDS = ('yr_legacy_amount', 'yr_migration_date')
FR_TITLES = [
    ('base.res_partner_title_madam', 'Madame', 'Mme'), ('base.res_partner_title_miss', 'Mademoiselle', 'Mlle'),
    ('base.res_partner_title_mister', 'Monsieur', 'M.'), ('base.res_partner_title_doctor', 'Docteur', 'Dr'),
    ('base.res_partner_title_prof', 'Professeur', 'Pr'),
]


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Already in Fidélité & CRM and reused: birth_day / birth_month / birth_year, customer_code (= card number,
    # also the barcode scanned at the POS), crm_store_id, crm_first_order_date…
    yr_gender = fields.Selection([('f', 'Femme'), ('h', 'Homme')], 'Sexe')
    # civilité = the standard « title » (list Madame, Mademoiselle, Monsieur… editable in Configuration › Civilités)
    yr_old_title_id = fields.Many2one('res.partner.title', 'Ancienne civilité', ondelete='set null',
                                      help='Civilité de l\'ancien système (même liste que la civilité).')
    yr_legacy_code = fields.Char('Code client fastmag', index=True, copy=False,
                                 help='Numéro de carte / numéro client dans fastmag.')
    yr_client_code = fields.Char('Code client fastmag (Y…)', index=True, copy=False,
                                 help='Code client des fichiers de ventes fastmag (ex. Y88074).')
    yr_legacy_old_code = fields.Char('Ancien code client (fastmag)', copy=False)
    yr_entry_date = fields.Date('Date d\'entrée (adhésion)')
    yr_first_purchase_legacy = fields.Date('Premier achat (fastmag)')
    yr_seller_code = fields.Char('Vendeuse (fastmag)')
    yr_seller_id = fields.Many2one('hr.employee', 'Créé par (vendeuse)', index=True,
                                   help='Vendeuse qui a créé la fiche dans fastmag (code vendeuse du fichier).')
    yr_legacy_segment = fields.Char('Segment fastmag', help='Ex. FID, OC, PA, MO')
    yr_npai = fields.Boolean('NPAI', help='N\'habite pas à l\'adresse indiquée (courrier revenu).')

    # purchases made before Posify: frozen once set, visible to the « données de migration » group only
    yr_legacy_amount = fields.Monetary('Montant TTC à la migration', currency_field='yr_currency_id', readonly=True,
                                       copy=False, groups='yr_data_migration.group_migration_data')
    yr_migration_date = fields.Date('Date de migration', readonly=True, copy=False,
                                    groups='yr_data_migration.group_migration_data')
    yr_currency_id = fields.Many2one('res.currency', compute='_compute_yr_currency_id')

    # « chiffre d'affaires clients depuis 2 ans » file: purchase lines, counted by Fidélité & CRM
    yr_legacy_purchase_ids = fields.One2many('yr.legacy.purchase', 'partner_id', 'Achats fastmag')

    def init(self):
        super().init()
        # French names of the standard civilities when the database is in French and they are not translated
        if not self.env['res.lang'].search_count([('code', '=', 'fr_FR'), ('active', '=', True)]):
            return
        for xmlid, name, shortcut in FR_TITLES:
            title = self.env.ref(xmlid, raise_if_not_found=False)
            if title:
                fr = title.with_context(lang='fr_FR')
                english = title.with_context(lang='en_US')
                if fr.name == english.name:
                    fr.write({'name': name, 'shortcut': shortcut})

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
