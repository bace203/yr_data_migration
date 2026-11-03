# -*- coding: utf-8 -*-
"""« Réf. fastmag » is now its own field (the « Référence interne » is the Sage X3 reference): filled for the articles
already imported from the fastmag sales history (the reference most used on the sales lines linked to each article)."""


def migrate(cr, version):
    cr.execute("""
        UPDATE product_template pt SET yr_fastmag_code = x.ref
          FROM (SELECT DISTINCT ON (pp.product_tmpl_id) pp.product_tmpl_id AS tmpl, l.product_ref AS ref
                  FROM yr_legacy_sale_line l
                  JOIN product_product pp ON pp.id = l.product_id
                 WHERE COALESCE(l.product_ref, '') <> '' AND NOT COALESCE(l.is_stamp, FALSE)
                 GROUP BY pp.product_tmpl_id, l.product_ref
                 ORDER BY pp.product_tmpl_id, COUNT(*) DESC) x
         WHERE pt.id = x.tmpl AND COALESCE(pt.yr_fastmag_code, '') = ''
    """)
