# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ResCompany(models.Model):
    _inherit = 'res.company'

    yr_fastmag_code = fields.Char(
        'Code magasin fastmag', compute='_compute_yr_fastmag_code', inverse='_inverse_yr_fastmag_code',
        help='Code du magasin de cette société dans les fichiers de ventes fastmag (ex. YR_MAHSOUNA). Plusieurs codes : '
             'séparés par une virgule (YR_MAHSOUNA,YR_MAHSN). C\'est le champ « Code magasin fastmag » du magasin de '
             'la société.')

    def _yr_stores(self):
        stores = self.env['loyalty.store'].sudo().with_context(active_test=False).search(
            [('company_id', 'in', self.ids)], order='sequence, id')
        out = {}
        for store in stores:
            out.setdefault(store.company_id.id, store)          # the first store of each company
        return out

    @api.depends('name')
    def _compute_yr_fastmag_code(self):
        stores = self._yr_stores()
        for company in self:
            store = stores.get(company.id or company._origin.id)
            company.yr_fastmag_code = store.yr_fastmag_code if store else False

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
