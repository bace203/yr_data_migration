# -*- coding: utf-8 -*-
"""NPAI is now the CRM field « NPAI (courrier revenu) » (usable in segments): the imported values are copied."""


def migrate(cr, version):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = 'res_partner' AND column_name = 'yr_npai'")
    if cr.fetchone():
        cr.execute("UPDATE res_partner SET crm_npai = TRUE WHERE yr_npai AND NOT COALESCE(crm_npai, FALSE)")
