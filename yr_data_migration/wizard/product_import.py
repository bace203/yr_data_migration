# -*- coding: utf-8 -*-
"""Fidélité & CRM › Import articles: a fastmag article file gets the complete fastmag import (Fiche fastmag tab,
axe › sous-axe, supplier…), whichever screen is used."""
from odoo import models


class LoyaltyProductImport(models.TransientModel):
    _inherit = 'loyalty.product.import'

    def action_import(self):
        self.ensure_one()
        # only this screen: the reception / stock count imports inherit it and keep their own behaviour
        if self._name == 'loyalty.product.import':
            fastmag = self.env['yr.migration.import'].create({'file': self.file, 'filename': self.filename})
            if fastmag.file_type == 'article':
                fastmag.update_prices = self.update_prices
                fastmag.action_import()
                self.write({'state': 'done', 'result': fastmag.result})
                return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id,
                        'view_mode': 'form', 'target': 'new'}
            fastmag.unlink()
        return super().action_import()
