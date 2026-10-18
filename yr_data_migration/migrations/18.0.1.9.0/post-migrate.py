# -*- coding: utf-8 -*-
"""Reasons (« Motif ») of the imported sales lines become sale motifs (generic), also on the POS order lines."""
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['yr.legacy.sale.line']._link_motifs()
