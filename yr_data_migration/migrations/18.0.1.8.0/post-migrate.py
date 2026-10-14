# -*- coding: utf-8 -*-
"""The customer's sex moved to Fidélité & CRM (crm_gender): the values imported before are copied there."""


def migrate(cr, version):
    cr.execute("""SELECT 1 FROM information_schema.columns WHERE table_name = 'res_partner'
                   AND column_name IN ('yr_gender', 'crm_gender') HAVING count(*) = 2""")
    if cr.fetchone():
        cr.execute("""UPDATE res_partner SET crm_gender = yr_gender
                       WHERE yr_gender IN ('f', 'h') AND crm_gender IS NULL""")
