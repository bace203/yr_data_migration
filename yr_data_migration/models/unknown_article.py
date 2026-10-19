# -*- coding: utf-8 -*-
"""Articles of the imported sales that are not in the catalogue: one line per reference / barcode, with what the
sales file says about it (designation, axe, line, motifs…), to identify them and to export the list."""
import base64

from odoo import _, api, fields, models, tools

MAX_LINES = 100000


class YrUnknownArticle(models.Model):
    _name = 'yr.unknown.article'
    _description = 'Article inconnu (ventes fastmag)'
    _auto = False
    _order = 'amount desc'
    _rec_name = 'code'

    code = fields.Char('Référence / code-barres', readonly=True)
    product_ref = fields.Char('Réf. article', readonly=True)
    barcode = fields.Char('Code-barres', readonly=True)
    name = fields.Char('Désignation du fichier', readonly=True)
    axe = fields.Char('Axe', readonly=True)
    product_line = fields.Char('Ligne', readonly=True)
    lines = fields.Integer('Lignes de vente', readonly=True)
    tickets = fields.Integer('Tickets', readonly=True)
    shops = fields.Integer('Magasins', readonly=True)
    qty = fields.Float('Quantité', readonly=True)
    amount = fields.Float('Montant TTC', readonly=True)
    avg_price = fields.Float('Prix moyen', readonly=True)
    avg_discount = fields.Float('Remise moyenne (%)', readonly=True)
    date_first = fields.Date('Première vente', readonly=True)
    date_last = fields.Date('Dernière vente', readonly=True)
    motifs = fields.Char('Motifs liés', readonly=True, help='Motifs des lignes de vente de cet article.')
    reasons = fields.Char('Motifs du fichier (texte)', readonly=True)
    in_catalog = fields.Boolean(
        'Dans le catalogue maintenant', readonly=True,
        help='L\'article existe depuis (importé après les ventes) : réimportez les ventes pour les rattacher.')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
            SELECT row_number() OVER (ORDER BY SUM(l.amount) DESC NULLS LAST, COALESCE(NULLIF(l.product_ref, ''), l.barcode))
                       AS id,
                   COALESCE(NULLIF(l.product_ref, ''), l.barcode) AS code,
                   MAX(NULLIF(l.product_ref, '')) AS product_ref,
                   MAX(NULLIF(l.barcode, '')) AS barcode,
                   MAX(l.name) AS name,
                   MAX(l.axe) AS axe,
                   MAX(l.product_line) AS product_line,
                   COUNT(*) AS lines,
                   COUNT(DISTINCT l.shop_code || '/' || l.ticket) AS tickets,
                   COUNT(DISTINCT l.shop_code) AS shops,
                   SUM(l.qty) AS qty,
                   SUM(l.amount) AS amount,
                   CASE WHEN SUM(l.qty) <> 0 THEN SUM(l.amount) / SUM(l.qty) END AS avg_price,
                   AVG(l.discount) AS avg_discount,
                   MIN(l.date) AS date_first,
                   MAX(l.date) AS date_last,
                   string_agg(DISTINCT m.name, ' ; ' ORDER BY m.name) AS motifs,
                   string_agg(DISTINCT l.reason, ' ; ' ORDER BY l.reason) AS reasons,
                   COALESCE(BOOL_OR(EXISTS (SELECT 1 FROM product_product p
                                             WHERE (l.product_ref IS NOT NULL AND p.default_code = l.product_ref)
                                                OR (l.barcode IS NOT NULL AND p.barcode = l.barcode))), FALSE) AS in_catalog
              FROM yr_legacy_sale_line l
              LEFT JOIN loyalty_motif m ON m.id = l.motif_id
             WHERE l.product_id IS NULL AND NOT COALESCE(l.is_stamp, FALSE)
               AND COALESCE(NULLIF(l.product_ref, ''), l.barcode) IS NOT NULL
             GROUP BY COALESCE(NULLIF(l.product_ref, ''), l.barcode)
            )
        """)

    def _line_domain(self):
        self.ensure_one()
        domain = [('product_id', '=', False), ('is_stamp', '=', False)]
        if self.product_ref:
            return domain + [('product_ref', '=', self.product_ref)]
        return domain + [('barcode', '=', self.barcode)]

    def action_open_lines(self):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': _('Lignes de %s', self.code),
                'res_model': 'yr.legacy.sale.line', 'view_mode': 'list,pivot', 'domain': self._line_domain()}

    @api.model
    def action_export_excel(self):
        """Excel: the unknown articles (one line each, with their motifs) and every sale line behind them."""
        import io
        self.env.cr.execute("""
            SELECT code, product_ref, barcode, name, axe, product_line, lines, tickets, shops, qty, amount, avg_price,
                   avg_discount, date_first, date_last, motifs, reasons, in_catalog
              FROM yr_unknown_article ORDER BY amount DESC NULLS LAST
        """)
        articles = [[r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8], float(r[9] or 0), float(r[10] or 0),
                     float(r[11] or 0), float(r[12] or 0), str(r[13] or ''), str(r[14] or ''), r[15], r[16],
                     _('oui') if r[17] else _('non')] for r in self.env.cr.fetchall()]
        self.env.cr.execute("""
            SELECT l.date, l.shop_code, l.ticket, l.product_ref, l.barcode, l.name, l.axe, l.product_line, l.qty,
                   l.price_unit, l.discount, l.amount, m.name, l.reason, l.comment, l.seller_name, l.cashier_name,
                   l.card, l.legacy_client_id
              FROM yr_legacy_sale_line l LEFT JOIN loyalty_motif m ON m.id = l.motif_id
             WHERE l.product_id IS NULL AND NOT COALESCE(l.is_stamp, FALSE)
               AND COALESCE(NULLIF(l.product_ref, ''), l.barcode) IS NOT NULL
             ORDER BY l.date DESC, l.ticket LIMIT %s
        """, [MAX_LINES + 1])
        rows = self.env.cr.fetchall()
        lines = [[str(r[0]), r[1], r[2], r[3], r[4], r[5], r[6], r[7], float(r[8] or 0), float(r[9] or 0),
                  float(r[10] or 0), float(r[11] or 0), r[12], r[13], r[14], r[15], r[16], r[17], r[18]]
                 for r in rows[:MAX_LINES]]
        sheets = [
            {'name': _('Articles inconnus'), 'columns': [
                _('Référence / code-barres'), _('Réf. article'), _('Code-barres'), _('Désignation du fichier'), _('Axe'),
                _('Ligne'), _('Lignes de vente'), _('Tickets'), _('Magasins'), _('Quantité'), _('Montant TTC'),
                _('Prix moyen'), _('Remise moyenne (%)'), _('Première vente'), _('Dernière vente'), _('Motifs liés'),
                _('Motifs du fichier'), _('Dans le catalogue maintenant')], 'rows': articles},
            {'name': _('Lignes de vente'), 'columns': [
                _('Date'), _('Magasin fastmag'), _('Ticket'), _('Réf. article'), _('Code-barres'), _('Désignation'),
                _('Axe'), _('Ligne'), _('Quantité'), _('Prix'), _('Remise (%)'), _('Total TTC'), _('Motif'),
                _('Motif (texte du fichier)'), _('Commentaire'), _('Vendeur'), _('Caissier'), _('Carte'),
                _('Code client')], 'rows': lines},
        ]
        if len(rows) > MAX_LINES:
            sheets.append({'name': _('Infos'), 'columns': [_('Attention')], 'rows': [[_(
                'Lignes limitées aux %s plus récentes.', MAX_LINES)]]})
        result = self.env['loyalty.crm.dashboard'].export_xlsx(sheets, 'articles_inconnus_fastmag')
        attachment = self.env['ir.attachment'].create({
            'name': result['filename'], 'datas': result['data'],
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
        return {'type': 'ir.actions.act_url', 'url': '/web/content/%s?download=true' % attachment.id, 'target': 'self'}
