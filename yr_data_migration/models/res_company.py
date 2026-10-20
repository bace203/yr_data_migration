# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    yr_store_ids = fields.One2many('loyalty.store', 'company_id', 'Magasins')
    yr_fastmag_code = fields.Char(
        'Code magasin fastmag', compute='_compute_yr_fastmag_code', inverse='_inverse_yr_fastmag_code', store=True,
        help='Code du magasin de cette société dans les fichiers de ventes fastmag (ex. YR_MAHSOUNA). Plusieurs codes : '
             'séparés par une virgule (YR_MAHSOUNA,YR_MAHSN). C\'est le champ « Code magasin fastmag » du magasin de '
             'la société.')
    yr_store_number = fields.Char('N° magasin', compute='_compute_yr_fastmag_code', store=True,
                                  help='Numéro du magasin de cette société (champ « Code » du magasin).')
    yr_store_sort = fields.Integer('N° magasin', compute='_compute_yr_fastmag_code', store=True,
                                   help='Le même numéro, pour trier la liste dans l\'ordre 1, 2, 3… 10, 11.')

    def _yr_stores(self):
        stores = self.env['loyalty.store'].sudo().with_context(active_test=False).search(
            [('company_id', 'in', self.ids)], order='sequence, id')
        out = {}
        for store in stores:
            out.setdefault(store.company_id.id, store)          # the first store of each company
        return out

    @api.depends('name', 'yr_store_ids.code', 'yr_store_ids.yr_fastmag_code', 'yr_store_ids.sequence')
    def _compute_yr_fastmag_code(self):
        stores = self._yr_stores()
        for company in self:
            store = stores.get(company.id or company._origin.id)
            company.yr_fastmag_code = store.yr_fastmag_code if store else False
            company.yr_store_number = store.code if store else False
            digits = ''.join(ch for ch in (store.code or '') if ch.isdigit()) if store else ''
            company.yr_store_sort = int(digits) if digits and (store.code or '').strip().isdigit() else 0

    def _inverse_yr_fastmag_code(self):
        stores = self._yr_stores()
        for company in self:
            store = stores.get(company.id)
            if not store:
                if company.yr_fastmag_code:
                    raise UserError(_('La société « %s » n\'a pas de magasin (Fidélité & CRM › Configuration › '
                                      'Magasins) : créez-le d\'abord.', company.name))
                continue
            store.yr_fastmag_code = (company.yr_fastmag_code or '').strip() or False
