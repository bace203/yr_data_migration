# -*- coding: utf-8 -*-
"""History sessions were named « Till/FASTMAG-<id> »: Posify reads the number after the last « / » to name the next
session of that till, so the till failed to open (« invalid literal for int() »). Rename them « Till/FASTMAG/00000 »."""


def migrate(cr, version):
    cr.execute("""
        UPDATE pos_session s
           SET name = regexp_replace(s.name, '/FASTMAG-[0-9]+$', '') || '/FASTMAG/00000'
         WHERE s.yr_fastmag AND s.name ~ '/FASTMAG-[0-9]+$'
           AND NOT EXISTS (SELECT 1 FROM pos_session o WHERE o.id <> s.id
                              AND o.name = regexp_replace(s.name, '/FASTMAG-[0-9]+$', '') || '/FASTMAG/00000')
    """)
