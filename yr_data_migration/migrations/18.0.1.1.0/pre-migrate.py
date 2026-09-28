# -*- coding: utf-8 -*-
"""The seller of a POS order is now an employee (was a user): the old values are not employees."""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns WHERE table_name = 'pos_order' AND column_name = 'yr_seller_id'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        SELECT con.conname FROM pg_constraint con
          JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY(con.conkey)
         WHERE con.conrelid = 'pos_order'::regclass AND con.contype = 'f' AND att.attname = 'yr_seller_id'
    """)
    for (name,) in cr.fetchall():
        cr.execute('ALTER TABLE pos_order DROP CONSTRAINT "%s"' % name)
    cr.execute('UPDATE pos_order SET yr_seller_id = NULL WHERE yr_seller_id IS NOT NULL')
