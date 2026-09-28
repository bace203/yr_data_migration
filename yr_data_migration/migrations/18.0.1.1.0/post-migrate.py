# -*- coding: utf-8 -*-
"""The existing tills ask for the seller before payment."""


def migrate(cr, version):
    cr.execute("UPDATE pos_config SET yr_seller_mode = 'required'")
