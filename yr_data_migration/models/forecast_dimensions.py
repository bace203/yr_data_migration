# -*- coding: utf-8 -*-
from odoo import _, models


class LoyaltyCrmForecastModel(models.Model):
    _inherit = 'loyalty.crm.forecast.model'

    def _dimensions(self):
        """The fields of the articles from the old system are other ways to break the sales down: the test finds
        which one predicts best (the season of a sous-axe « Rouge à lèvres » is not the one of an axe « Maquillage »)."""
        dims = super()._dimensions()
        dims.update({
            'axe': {'label': _('Axe'), 'sql': 'pt.yr_axe_id::text', 'category': True},
            'sous_axe': {'label': _('Sous-axe'), 'sql': 'pt.yr_sub_axe_id::text', 'category': True},
            'nature': {'label': _('Nature'), 'sql': 'NULLIF(pt.yr_nature, \'\')', 'category': False},
            'marque': {'label': _('Marque'), 'sql': 'NULLIF(pt.yr_brand, \'\')', 'category': False},
            'ligne': {'label': _('Ligne'), 'sql': 'NULLIF(pt.yr_line, \'\')', 'category': False},
            'conditionnement': {'label': _('Conditionnement (contenance)'), 'sql': 'NULLIF(pt.yr_packaging, \'\')',
                                'category': False},
            'genre': {'label': _('Genre'), 'sql': 'NULLIF(pt.yr_gender, \'\')', 'category': False},
        })
        return dims
