# -*- coding: utf-8 -*-
"""Sales imported before 18.0.1.5.0 used the fastmag customer code (Y88074) as card number: it is a customer code.

The lines keep it as « code client fastmag » (their customer is found again by importing the « Liste client »
file); the purchase history built on those codes (no customer behind them) is removed.
"""


def migrate(cr, version):
    cr.execute(r"""
        UPDATE yr_legacy_sale_line
           SET legacy_client_id = upper(card), card = NULL, partner_id = NULL
         WHERE card ~* '^Y\d+$'
    """)
    cr.execute(r"""
        UPDATE yr_legacy_sale_line SET legacy_client_id = 'Y' || legacy_client_id
         WHERE legacy_client_id ~ '^\d+$' AND legacy_client_id !~ '^0+$'
    """)
    cr.execute(r"DELETE FROM yr_legacy_purchase WHERE card ~* '^Y\d+$' AND partner_id IS NULL")
