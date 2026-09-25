# -*- coding: utf-8 -*-
"""fastmag purchase history (« CA clients » file): one line per customer, day and store.

The lines are added to the CRM order view (loyalty.crm.order, source « fastmag »), so the customer status, first /
last purchase, turnover, segments and dashboards of Fidélité & CRM include the purchases made before Odoo.
"""
from odoo import api, fields, models
from odoo.tools import SQL


class YrLegacyPurchase(models.Model):
    _name = 'yr.legacy.purchase'
    _description = 'Achat fastmag (historique)'
    _order = 'date desc, id desc'

    card = fields.Char('Carte fidélité', required=True, index=True)
    partner_id = fields.Many2one('res.partner', 'Client', index=True, ondelete='cascade')
    date = fields.Datetime('Date', required=True, index=True)
    shop_code = fields.Char('Magasin fastmag')
    store_id = fields.Many2one('loyalty.store', 'Magasin', index=True)
    company_id = fields.Many2one('res.company', 'Société', required=True, default=lambda self: self.env.company)
    amount = fields.Float('Montant TTC', digits='Product Price')
    legacy_client_id = fields.Char('N° client fastmag')

    _sql_constraints = [('visit_unique', 'unique(card, date, shop_code)',
                         'Un seul achat par carte, jour et magasin.')]

    @api.model
    def _link_partners(self, cards=None):
        """Attach the lines to the customers (card = customer number); returns the customers concerned."""
        self.flush_model()
        self.env['res.partner'].flush_model(['customer_code', 'yr_legacy_code'])
        where = SQL('l.card = ANY(%s)', list(cards)) if cards is not None else SQL('TRUE')
        self.env.cr.execute(SQL("""
            UPDATE yr_legacy_purchase l SET partner_id = p.id
              FROM res_partner p
             WHERE (p.customer_code = l.card OR p.yr_legacy_code = l.card)
               AND l.partner_id IS DISTINCT FROM p.id AND %s
            RETURNING p.id
        """, where))
        partner_ids = {row[0] for row in self.env.cr.fetchall()}
        self.invalidate_model(['partner_id'])
        return partner_ids


class LoyaltyCrmOrder(models.Model):
    _inherit = 'loyalty.crm.order'

    source = fields.Selection(selection_add=[('fastmag', 'Historique fastmag')])

    def _select_sql(self):
        # negative ids: POS tickets use 2n and sale orders 2n + 1
        return super()._select_sql() + """
            UNION ALL
            SELECT -l.id AS id,
                   'fastmag ' || COALESCE(l.shop_code, '') AS reference,
                   'fastmag' AS source,
                   NULL::integer AS pos_order_id,
                   NULL::integer AS sale_order_id,
                   l.partner_id AS partner_id,
                   TRUE AS is_identified,
                   FALSE AS is_crm,
                   l.date AS date,
                   l.company_id AS company_id,
                   l.store_id AS store_id,
                   'retail' AS channel,
                   l.amount AS amount_total,
                   0 AS discount_amount,
                   1 AS nb_order
              FROM yr_legacy_purchase l
             WHERE l.partner_id IS NOT NULL
        """


class LoyaltyCrmEngine(models.AbstractModel):
    _inherit = 'loyalty.crm.engine'

    @api.model
    def _refresh_metrics(self, partner_ids=None):
        super()._refresh_metrics(partner_ids)
        if partner_ids is not None and not partner_ids:
            return
        # first purchase known from the customer files (older than the 2-year history)
        where = SQL('TRUE') if partner_ids is None else SQL('p.id = ANY(%s)', list(partner_ids))
        self.env.cr.execute(SQL("""
            UPDATE res_partner p
               SET crm_first_order_date = LEAST(COALESCE(p.crm_first_order_date, p.yr_first_purchase_legacy),
                                                p.yr_first_purchase_legacy),
                   crm_last_order_date = COALESCE(p.crm_last_order_date, p.yr_first_purchase_legacy),
                   crm_order_count = GREATEST(p.crm_order_count, 1)
             WHERE p.yr_first_purchase_legacy IS NOT NULL AND %s
               AND (p.crm_first_order_date IS NULL OR p.crm_first_order_date > p.yr_first_purchase_legacy
                    OR p.crm_order_count = 0)
        """, where))
