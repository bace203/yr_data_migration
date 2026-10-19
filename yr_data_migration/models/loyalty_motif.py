# -*- coding: utf-8 -*-
from odoo import models


class LoyaltyMotif(models.Model):
    _inherit = 'loyalty.motif'

    def _campaign_spans(self):
        """Also the imported history whose POS orders are not made yet (they are made in the background)."""
        spans = super()._campaign_spans()
        self.env.cr.execute("""
            SELECT motif_id, MIN(date), MAX(date), COUNT(DISTINCT shop_code || '/' || ticket)
              FROM yr_legacy_sale_line WHERE motif_id = ANY(%s) GROUP BY motif_id
        """, [self.ids])
        for motif_id, first, last, tickets in self.env.cr.fetchall():
            old = spans.get(motif_id)
            spans[motif_id] = (min(first, old[0]), max(last, old[1]), max(tickets, old[2])) if old else (
                first, last, tickets)
        return spans
