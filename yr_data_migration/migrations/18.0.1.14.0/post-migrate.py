# -*- coding: utf-8 -*-
"""18.0.1.14: the lines of the fastmag history are counted as delivered (they have no delivery in Posify).
The coupon lines (left out by the imports made before) come with a new import of the same files: the missing
line is added to its ticket and the order of the ticket is made again."""


def migrate(cr, version):
    cr.execute("""
        UPDATE pos_order_line SET qty_delivered = qty
         WHERE yr_fastmag_line_id IS NOT NULL AND COALESCE(qty_delivered, 0) <> COALESCE(qty, 0)
    """)
