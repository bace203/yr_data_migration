# -*- coding: utf-8 -*-
"""fastmag customer codes (« Liste client » file): code client Y… ↔ loyalty card number.

The sales files only give the fastmag customer code (Y88074, or 88074): this table finds the card, hence the
customer. Codes without a real card are kept here (their sales stay anonymous) but never become customers.
"""
from odoo import api, fields, models
from odoo.tools import SQL


class YrClientCode(models.Model):
    _name = 'yr.client.code'
    _description = 'Code client fastmag'
    _order = 'id'
    _rec_name = 'code'

    code = fields.Char('Code client fastmag', required=True, index=True, help='Ex. Y88074')
    card = fields.Char('Carte fidélité', index=True, help='Vide : pas de vraie carte (non importé comme client).')
    name = fields.Char('Nom fastmag')
    date = fields.Date('Date de création')
    points = fields.Float('Points fidélité fastmag')
    category = fields.Char('Catégorie')
    partner_id = fields.Many2one('res.partner', 'Client', index=True, ondelete='set null')

    _sql_constraints = [('code_unique', 'unique(code)', 'Un code client fastmag ne figure qu\'une fois.')]

    @api.model
    def _cards_for(self, codes):
        """{code: card} of the given codes (only the codes with a card)."""
        found = {}
        codes = list(codes)
        for start in range(0, len(codes), 20000):
            self.env.cr.execute(SQL('SELECT code, card FROM yr_client_code WHERE code = ANY(%s) AND card IS NOT NULL',
                                    codes[start:start + 20000]))
            found.update(self.env.cr.fetchall())
        return found

    @api.model
    def _codes_for(self, cards):
        """{card: code} of the given cards."""
        found = {}
        cards = list(cards)
        for start in range(0, len(cards), 20000):
            self.env.cr.execute(SQL('SELECT card, code FROM yr_client_code WHERE card = ANY(%s)',
                                    cards[start:start + 20000]))
            found.update(self.env.cr.fetchall())
        return found

    @api.model
    def _link_partners(self, cards=None):
        """Code ↔ customer (card = customer number); the customer gets its fastmag code."""
        self.flush_model()
        self.env['res.partner'].flush_model(['customer_code', 'yr_legacy_code', 'yr_client_code'])
        where = SQL('c.card = ANY(%s)', list(cards)) if cards is not None else SQL('c.card IS NOT NULL')
        self.env.cr.execute(SQL("""
            UPDATE yr_client_code c SET partner_id = p.id
              FROM res_partner p
             WHERE (p.customer_code = c.card OR p.yr_legacy_code = c.card)
               AND c.partner_id IS DISTINCT FROM p.id AND %s
        """, where))
        self.env.cr.execute(SQL("""
            UPDATE res_partner p SET yr_client_code = c.code
              FROM yr_client_code c
             WHERE c.partner_id = p.id AND p.yr_client_code IS NULL AND %s
        """, where))
        self.invalidate_model(['partner_id'])
        self.env['res.partner'].invalidate_model(['yr_client_code'])
