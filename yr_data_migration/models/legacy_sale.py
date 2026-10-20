# -*- coding: utf-8 -*-
"""fastmag sales detail (« Détail ventes » file): one line per ticket line, with the cashier (Utilisateur) and the
seller (Vendeur). The totals per customer, day and store also feed the purchase history (yr.legacy.purchase)."""
import logging
import re

import psycopg2
import time
from collections import defaultdict
from datetime import datetime, time as dtime

from odoo import _, api, fields, models
from odoo.modules import module as odoo_module
from odoo.tools import SQL

_logger = logging.getLogger(__name__)
UNKNOWN_PRODUCT_CODE = 'FASTMAG-INCONNU'
STAMP_PRODUCT_CODES = ('DTT', 'TIMBRE', 'FASTMAG-DTT')
POS_BATCH = 1000                       # tickets per batch (commit between batches)


def name_key(value):
    return ' '.join(str(value or '').upper().split())


class YrLegacySaleLine(models.Model):
    _name = 'yr.legacy.sale.line'
    _description = 'Vente fastmag (détail)'
    _order = 'date desc, ticket desc, sequence, id'
    _rec_name = 'ticket'

    shop_code = fields.Char('Magasin fastmag', required=True, index=True)
    store_id = fields.Many2one('loyalty.store', 'Magasin', index=True)
    pos_config_id = fields.Many2one('pos.config', 'Point de vente', index=True,
                                    help='Caisse (point de vente) du magasin de la vente.')
    company_id = fields.Many2one('res.company', 'Société', required=True, default=lambda self: self.env.company)
    ticket = fields.Char('Ticket', required=True, index=True)
    sequence = fields.Integer('N° de ligne', default=1)
    date = fields.Date('Date', required=True, index=True)
    cashier_name = fields.Char('Caissier', index=True, help='Utilisateur fastmag qui a encaissé (nom du fichier).')
    cashier_id = fields.Many2one('hr.employee', 'Caissier (employé)', index=True)
    seller_name = fields.Char('Vendeur', index=True, help='Vendeur fastmag (nom du fichier).')
    seller_id = fields.Many2one('hr.employee', 'Vendeur (employé)', index=True)
    card = fields.Char('Carte fidélité', index=True)
    legacy_client_id = fields.Char('Code client fastmag', index=True, help='Ex. Y88074.')
    partner_id = fields.Many2one('res.partner', 'Client', index=True)
    product_ref = fields.Char('Réf. article')
    barcode = fields.Char('Code-barres')
    product_id = fields.Many2one('product.product', 'Article', index=True)
    name = fields.Char('Désignation')
    axe = fields.Char('Axe')
    product_line = fields.Char('Ligne')
    is_stamp = fields.Boolean('Droit de timbre')
    qty = fields.Float('Quantité', digits='Product Unit of Measure')
    price_unit = fields.Float('Prix', digits='Product Price')
    discount = fields.Float('Remise (%)')
    amount = fields.Float('Total TTC', digits='Product Price')
    reason = fields.Char('Motif (texte du fichier)')
    motif_id = fields.Many2one('loyalty.motif', 'Motif', index='btree_not_null', ondelete='set null')
    comment = fields.Char('Commentaire')
    pos_error = fields.Char('Erreur commande PdV', index='btree_not_null', copy=False,
                            help='Pourquoi la commande de ce ticket n\'a pas pu être créée. « Créer les commandes PdV » '
                            '(Paramètres) réessaie.')
    pos_order_id = fields.Many2one('pos.order', 'Commande PdV', index='btree_not_null', ondelete='set null',
                                   copy=False, help='Commande du point de vente créée pour ce ticket.')

    _sql_constraints = [('line_unique', 'unique(shop_code, ticket, sequence)',
                         'Une seule ligne par magasin, ticket et n° de ligne.')]

    @api.model
    @api.model
    def _motif_chain(self, reason):
        """Motifs of a reason typed « A ; B » : all of them when the setting « Ticket avec plusieurs offres » counts
        every campaign, else only the first."""
        Motif = self.env['loyalty.motif'].sudo()
        motifs = [Motif._for_name(name) for name in (reason or '').split(';')]
        motifs = [m for m in motifs if m]
        rule = self.env['ir.config_parameter'].sudo().get_param('loyalty_tier_marketing.allocation_rule', 'first')
        return motifs if rule == 'all' else motifs[:1]

    @api.model
    def _link_motifs(self):
        """Lines with a reason in the file but no motif yet: each motif of the reason (several separated by « ; »)
        is created (generic) and linked; the first is the main one. Also on the POS order lines already created."""
        cr = self.env.cr
        cr.execute("SELECT DISTINCT reason FROM yr_legacy_sale_line WHERE motif_id IS NULL AND reason IS NOT NULL")
        for (reason,) in cr.fetchall():
            motifs = self._motif_chain(reason)
            if not motifs:
                continue
            cr.execute("UPDATE yr_legacy_sale_line SET motif_id = %s WHERE motif_id IS NULL AND reason = %s",
                       [motifs[0].id, reason])
            cr.execute("SELECT id FROM yr_legacy_sale_line WHERE motif_id = %s AND reason = %s", [motifs[0].id, reason])
            line_ids = [row[0] for row in cr.fetchall()]
            for start in range(0, len(line_ids), 20000):
                cr.execute("""
                    INSERT INTO pos_line_motif_rel (line_id, motif_id)
                    SELECT pl.id, m FROM pos_order_line pl, unnest(%s::int[]) AS m
                     WHERE pl.yr_fastmag_line_id = ANY(%s)
                    ON CONFLICT DO NOTHING
                """, [[m.id for m in motifs], line_ids[start:start + 20000]])
        cr.execute("""
            UPDATE pos_order_line pl SET crm_motif_id = l.motif_id
              FROM yr_legacy_sale_line l
             WHERE pl.yr_fastmag_line_id = l.id AND l.motif_id IS NOT NULL AND pl.crm_motif_id IS NULL
        """)
        self.invalidate_model(['motif_id'])
        self.env['pos.order.line'].invalidate_model(['crm_motif_id', 'crm_motif_ids'])

    def _link_partners_by_code(self, codes):
        """Lines whose fastmag client code (Y…) is the code of an imported customer: linked to it (also the POS orders
        already made). The code tells apart two customers who share a card."""
        codes = list(codes or [])
        if not codes:
            return
        self.flush_model()
        self.env['res.partner'].flush_model(['yr_client_code'])
        self.env.cr.execute(SQL("""
            UPDATE yr_legacy_sale_line l SET partner_id = p.id
              FROM res_partner p
             WHERE p.yr_client_code = l.legacy_client_id AND l.legacy_client_id = ANY(%s)
               AND l.partner_id IS DISTINCT FROM p.id
        """, codes))
        self.invalidate_model(['partner_id'])
        self.env['pos.order'].flush_model(['partner_id'])
        self.env.cr.execute(SQL("""
            UPDATE pos_order o SET partner_id = l.partner_id
              FROM yr_legacy_sale_line l
             WHERE l.pos_order_id = o.id AND l.legacy_client_id = ANY(%s) AND l.partner_id IS NOT NULL
               AND o.partner_id IS DISTINCT FROM l.partner_id
        """, codes))
        self.env['pos.order'].invalidate_model(['partner_id'])

    def _link_partners(self, cards=None):
        self.flush_model()
        self.env['res.partner'].flush_model(['customer_code', 'yr_legacy_code'])
        where = SQL('l.card = ANY(%s)', list(cards)) if cards is not None else SQL('l.card IS NOT NULL')
        self.env.cr.execute(SQL("""
            UPDATE yr_legacy_sale_line l SET partner_id = p.id
              FROM res_partner p
             WHERE (p.customer_code = l.card OR p.yr_legacy_code = l.card)
               AND l.partner_id IS DISTINCT FROM p.id AND %s
        """, where))
        self.invalidate_model(['partner_id'])
        # the POS orders already made from these tickets follow (customer found later, by its card or code Y)
        self.env['pos.order'].flush_model(['partner_id', 'yr_fastmag_card'])
        self.env.cr.execute(SQL("""
            UPDATE pos_order o SET partner_id = l.partner_id, yr_fastmag_card = l.card
              FROM yr_legacy_sale_line l
             WHERE l.pos_order_id = o.id AND l.card IS NOT NULL
               AND (o.partner_id IS DISTINCT FROM l.partner_id OR o.yr_fastmag_card IS DISTINCT FROM l.card)
               AND %s
        """, where))
        self.env['pos.order'].invalidate_model(['partner_id', 'yr_fastmag_card'])

    @api.model
    def _employee_index(self):
        """Upper-cased name / fastmag names → employee."""
        index = {}
        for employee in self.env['hr.employee'].sudo().with_context(active_test=False).search([]):
            for alias in (employee.yr_fastmag_name or '').split(','):
                if name_key(alias):
                    index[name_key(alias)] = employee
        for employee in self.env['hr.employee'].sudo().search([]):
            index.setdefault(name_key(employee.name), employee)
        return index

    @api.model
    def _link_employees(self):
        """Attach cashiers and sellers known by their fastmag name (after creating / renaming employees)."""
        index = self._employee_index()
        count = 0
        for field, name_field in (('seller_id', 'seller_name'), ('cashier_id', 'cashier_name')):
            groups = self._read_group([(field, '=', False), (name_field, '!=', False)], [name_field])
            for (name,) in groups:
                employee = index.get(name_key(name))
                if employee:
                    lines = self.search([(field, '=', False), (name_field, '=', name)])
                    lines.write({field: employee.id})
                    count += len(lines)
        self._yr_sync_order_employees()
        return count

    @api.model
    def _yr_sync_order_employees(self):
        """The POS orders made from fastmag tickets follow their lines: seller (Vendeur) and cashier."""
        self.flush_model()
        self.env['pos.order'].flush_model()
        self.env.cr.execute("""
            UPDATE pos_order o SET yr_seller_id = l.seller_id, yr_seller_ref = l.seller_id
              FROM yr_legacy_sale_line l
             WHERE l.pos_order_id = o.id AND l.seller_id IS NOT NULL AND o.yr_seller_id IS DISTINCT FROM l.seller_id
        """)
        if 'employee_id' in self.env['pos.order']._fields:
            self.env.cr.execute("""
                UPDATE pos_order o SET employee_id = l.cashier_id
                  FROM yr_legacy_sale_line l
                 WHERE l.pos_order_id = o.id AND l.cashier_id IS NOT NULL
                   AND o.employee_id IS DISTINCT FROM l.cashier_id
            """)
        self.env['pos.order'].invalidate_model(['yr_seller_id', 'yr_seller_ref'] + (
            ['employee_id'] if 'employee_id' in self.env['pos.order']._fields else []))

    def action_link_employees(self):
        count = self._link_employees()
        return {
            'type': 'ir.actions.client', 'tag': 'display_notification',
            'params': {'type': 'success' if count else 'info', 'sticky': False,
                       'message': _('%s ligne(s) rattachée(s) à un employé.', count) if count else
                       _('Aucune nouvelle correspondance : renseignez le champ « Nom(s) fastmag » '
                                  'des employés.'),
                       'next': {'type': 'ir.actions.client', 'tag': 'soft_reload'}},
        }

    # ── fastmag tickets → Point de Vente orders ──────────────────────────
    # columns pointing to POS orders / lines without an index in Odoo: deleting 100 000s of orders would
    # read the whole table for each deleted line (stuck at 100 % CPU)
    FK_INDEXES = [
        ('pos_order_line', 'combo_parent_id'), ('pos_order_line', 'refunded_orderline_id'),
        ('pos_pack_operation_lot', 'pos_order_line_id'), ('product_attribute_custom_value', 'pos_order_line_id'),
        ('loyalty_card', 'source_pos_order_id'), ('loyalty_campaign_result', 'pos_order_id'),
        ('payment_transaction', 'pos_order_id'), ('account_move', 'reversed_pos_order_id'),
        ('account_payment', 'pos_order_id'), ('procurement_group', 'pos_order_id'),
    ]

    def init(self):
        super().init()
        self._yr_fk_indexes()

    @api.model
    def _yr_fk_indexes(self):
        cr = self.env.cr
        for table, column in self.FK_INDEXES:
            cr.execute("""SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s""",
                       (table, column))
            if not cr.fetchone():
                continue
            try:
                with cr.savepoint():
                    cr.execute(SQL('CREATE INDEX IF NOT EXISTS %s ON %s (%s) WHERE %s IS NOT NULL',
                                   SQL.identifier('%s_%s_yr_idx' % (table, column)), SQL.identifier(table),
                                   SQL.identifier(column), SQL.identifier(column)))
            except Exception as error:  # noqa: BLE001 - never blocks the update / deletion
                _logger.warning('fastmag: index %s.%s non créé : %s', table, column, error)

    @api.model
    def _yr_can_commit(self):
        return not odoo_module.current_test and not self.env.registry.in_test_mode()

    @api.model
    def _yr_link_stores_products(self):
        """Lines imported before their store or article existed: attached now (store codes, articles)."""
        self.flush_model()
        cr = self.env.cr
        stores = self.env['yr.migration.import']._stores()
        linked = {'stores': 0, 'products': 0}
        cr.execute('SELECT DISTINCT shop_code FROM yr_legacy_sale_line WHERE store_id IS NULL')
        for (shop,) in cr.fetchall():
            store = stores.get(shop)
            if store:
                config = store.pos_config_ids[:1]
                cr.execute(SQL("""
                    UPDATE yr_legacy_sale_line SET store_id = %s, company_id = %s, pos_config_id = %s
                     WHERE store_id IS NULL AND shop_code = %s
                """, store.id, store.company_id.id, config.id or None, shop))
                linked['stores'] += cr.rowcount
        for column in ('default_code', 'barcode'):
            source = 'product_ref' if column == 'default_code' else 'barcode'
            cr.execute(SQL("""
                UPDATE yr_legacy_sale_line l SET product_id = pp.id
                  FROM product_product pp
                 WHERE l.product_id IS NULL AND NOT COALESCE(l.is_stamp, FALSE) AND l.%s IS NOT NULL
                   AND pp.%s = l.%s
            """, SQL.identifier(source), SQL.identifier(column), SQL.identifier(source)))
            linked['products'] += cr.rowcount
        # orders already made with the « article non retrouvé » get the real article
        cr.execute("""
            UPDATE pos_order_line pl SET product_id = l.product_id
              FROM yr_legacy_sale_line l
             WHERE pl.yr_fastmag_line_id = l.id AND l.product_id IS NOT NULL AND pl.product_id <> l.product_id
        """)
        self.invalidate_model()
        self.env['pos.order.line'].invalidate_model(['product_id'])
        return linked

    @api.model
    def _yr_special_products(self):
        """« Article fastmag non retrouvé » and the stamp duty: lines of tickets whose article is unknown."""
        Product = self.env['product.product'].sudo().with_context(active_test=False)
        unknown = Product.search([('default_code', '=', UNKNOWN_PRODUCT_CODE)], limit=1) or Product.create({
            'name': _('Article fastmag (non retrouvé)'), 'default_code': UNKNOWN_PRODUCT_CODE, 'type': 'service',
            'sale_ok': False, 'available_in_pos': False, 'list_price': 0.0, 'taxes_id': [(5, 0, 0)],
            'company_id': False})
        stamp = Product.search([('default_code', 'in', STAMP_PRODUCT_CODES)], limit=1) or Product.create({
            'name': _('Droit de timbre (fastmag)'), 'default_code': 'FASTMAG-DTT', 'type': 'service',
            'sale_ok': False, 'available_in_pos': False, 'list_price': 0.0, 'taxes_id': [(5, 0, 0)],
            'company_id': False})
        return unknown, stamp

    @api.model
    def _yr_history_session(self, store, cache):
        """Closed « historique fastmag » session of the store's till (an archived till for a closed store)."""
        if store.id in cache:
            return cache[store.id]
        Config = self.env['pos.config'].sudo().with_context(active_test=False)
        config = Config.search([('crm_store_id', '=', store.id)], order='active desc, id', limit=1)
        if not config:
            company = store.company_id
            Warehouse = self.env['stock.warehouse'].sudo().with_company(company)
            if not Warehouse.search([('company_id', '=', company.id)], limit=1):
                # a closed store's company may have none: the till needs one (no stock is moved)
                code = re.sub(r'[^A-Z0-9]', '', (store.name or '').upper())[:5] or 'MAG'
                Warehouse.create({'name': store.name, 'code': code, 'company_id': company.id})
            config = Config.with_company(company).create({
                'name': _('%s (historique fastmag)', store.name), 'company_id': company.id,
                'crm_store_id': store.id, 'active': False,
                'payment_method_ids': [(6, 0, [])]})              # history: no payment
        Session = self.env['pos.session'].sudo()
        session = Session.search([('config_id', '=', config.id), ('yr_fastmag', '=', True)], limit=1)
        if not session:
            session = Session.with_company(config.company_id).with_context(onboarding_creation=True).create(
                {'config_id': config.id})
            session.write({'state': 'closed', 'stop_at': fields.Datetime.now(), 'yr_fastmag': True,
                           'name': '%s/FASTMAG-%s' % (config.name, config.id)})
        cache[store.id] = session
        return session

    @api.model
    def _yr_make_pos_orders(self, max_tickets=POS_BATCH):
        """Next tickets of the imported sales → Point de Vente orders (state « Comptabilisé », no payment,
        accounting entry nor stock move). Returns (orders created, more tickets left)."""
        self.flush_model()
        cr = self.env.cr
        # the history session of each store concerned (a store whose till cannot be made is skipped, logged)
        cr.execute('SELECT DISTINCT store_id FROM yr_legacy_sale_line WHERE pos_order_id IS NULL AND store_id IS NOT NULL')
        sessions, ready = {}, []
        for store in self.env['loyalty.store'].sudo().with_context(active_test=False).browse(
                [row[0] for row in cr.fetchall()]):
            try:
                with cr.savepoint():
                    self._yr_history_session(store, sessions)
                ready.append(store.id)
            except Exception as error:  # noqa: BLE001 - the other stores go on
                sessions.pop(store.id, None)
                _logger.warning('fastmag: pas de commandes PdV pour le magasin %s : %s', store.name, error)
        if not ready:
            return 0, False
        cr.execute(SQL("""
            SELECT shop_code, ticket FROM yr_legacy_sale_line
             WHERE pos_order_id IS NULL AND pos_error IS NULL AND store_id = ANY(%s)
             GROUP BY shop_code, ticket ORDER BY min(date), shop_code, ticket LIMIT %s
        """, ready, max_tickets))
        keys = set(cr.fetchall())
        if not keys:
            return 0, False
        cr.execute(SQL("""
            SELECT id, shop_code, ticket, sequence, date, store_id, partner_id, card, seller_id, seller_name,
                   cashier_id, cashier_name, product_id, is_stamp, name, product_ref, qty, price_unit, discount,
                   amount, motif_id
              FROM yr_legacy_sale_line
             WHERE pos_order_id IS NULL AND pos_error IS NULL AND store_id IS NOT NULL AND ticket = ANY(%s)
               AND shop_code = ANY(%s)
             ORDER BY shop_code, ticket, sequence, id
        """, list({t for _s, t in keys}), list({s for s, _t in keys})))
        tickets = defaultdict(list)
        for row in cr.dictfetchall():
            if (row['shop_code'], row['ticket']) in keys:
                tickets[(row['shop_code'], row['ticket'])].append(row)
        cr.execute("SELECT DISTINCT motif_id, reason FROM yr_legacy_sale_line WHERE motif_id = ANY(%s)",
                   [list({r['motif_id'] for rows in tickets.values() for r in rows if r['motif_id']})])
        motif_sets = {mid: [m.id for m in self._motif_chain(reason)] or [mid] for mid, reason in cr.fetchall()}
        unknown, stamp = self._yr_special_products()
        stores = {store.id: store for store in self.env['loyalty.store'].sudo().with_context(active_test=False)
                  .browse({rows[0]['store_id'] for rows in tickets.values()})}
        has_employee = 'employee_id' in self.env['pos.order']._fields
        vals_list, partner_ids, vals_by_key = [], set(), {}
        for number, ((shop, ticket), rows) in enumerate(sorted(tickets.items()), start=1):
            store = stores[rows[0]['store_id']]
            session = sessions[store.id]
            first = rows[0]
            partner = next((r['partner_id'] for r in rows if r['partner_id']), False)
            card = next((r['card'] for r in rows if r['card']), False)
            seller = next((r['seller_id'] for r in rows if r['seller_id']), False)
            cashier = next((r['cashier_id'] for r in rows if r['cashier_id']), False)
            total = sum(r['amount'] or 0.0 for r in rows)
            key = '%s/%s' % (shop, ticket)
            vals = {
                'session_id': session.id, 'name': key, 'pos_reference': _('fastmag %s', key),
                'date_order': datetime.combine(first['date'], dtime(12, 0)), 'partner_id': partner,
                'state': 'done', 'user_id': False, 'sequence_number': number,
                'amount_total': total, 'amount_tax': 0.0, 'amount_paid': total, 'amount_return': 0.0,
                'yr_fastmag_ticket': key, 'yr_fastmag_card': card, 'yr_seller_id': seller,
                'yr_seller_name': first['seller_name'], 'yr_cashier_name': first['cashier_name'],
                'lines': [(0, 0, {
                    'name': '%s/%s' % (key, r['sequence']),
                    'product_id': r['product_id'] or (stamp.id if r['is_stamp'] else unknown.id),
                    'full_product_name': r['name'] or r['product_ref'] or (stamp if r['is_stamp'] else unknown).name,
                    'qty': r['qty'] or 0.0, 'price_unit': r['price_unit'] or 0.0, 'discount': r['discount'] or 0.0,
                    'price_subtotal': r['amount'] or 0.0, 'price_subtotal_incl': r['amount'] or 0.0,
                    'tax_ids': [(6, 0, [])], 'yr_fastmag_line_id': r['id'],
                    'crm_motif_id': r['motif_id'] or False,
                    'crm_motif_ids': [(6, 0, motif_sets.get(r['motif_id'], [r['motif_id']] if r['motif_id'] else []))],
                }) for r in rows],
            }
            if has_employee:
                vals['employee_id'] = cashier
            vals_list.append(vals)
            vals_by_key[(shop, ticket)] = vals
            if partner:
                partner_ids.add(partner)
        Order = self.env['pos.order'].sudo().with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True)
        failed = {}
        try:
            with cr.savepoint():
                orders = Order.create(vals_list)
        except Exception as error:  # noqa: BLE001 - one bad ticket must not block the others: one by one
            _logger.warning('fastmag: lot de %s tickets en échec (%s) : essai ticket par ticket', len(vals_list), error)
            orders = Order
            for key, vals in vals_by_key.items():
                try:
                    with cr.savepoint():
                        orders |= Order.create([vals])
                except Exception as ticket_error:  # noqa: BLE001
                    failed[key] = str(ticket_error.args[0] if ticket_error.args else ticket_error)[:240]
        for (shop, ticket), message in failed.items():
            cr.execute('UPDATE yr_legacy_sale_line SET pos_error = %s WHERE shop_code = %s AND ticket = %s',
                       [message, shop, ticket])
            _logger.warning('fastmag: commande du ticket %s/%s non créée : %s', shop, ticket, message)
        self.env['pos.order.line'].flush_model()
        cr.execute(SQL("""
            UPDATE yr_legacy_sale_line l SET pos_order_id = pl.order_id
              FROM pos_order_line pl
             WHERE pl.yr_fastmag_line_id = l.id AND pl.order_id = ANY(%s)
        """, orders.ids))
        self.invalidate_model(['pos_order_id'])
        if partner_ids:
            self._yr_refresh_partners(partner_ids)
        cr.execute(SQL('SELECT 1 FROM yr_legacy_sale_line WHERE pos_order_id IS NULL AND pos_error IS NULL '
                       'AND store_id = ANY(%s) LIMIT 1', ready))
        return len(orders), bool(cr.fetchone())

    @api.model
    def _yr_refresh_partners(self, partner_ids):
        """Customer statistics of Fidélité & CRM. An import and the background order creation may refresh the
        same customers at the same time (« could not serialize access »): the work done is saved first, then
        the refresh is retried in a new transaction; if it still collides, the nightly full refresh catches up."""
        engine = self.env['loyalty.crm.engine'].sudo()
        partner_ids = list(partner_ids)
        if not self._yr_can_commit():
            engine.refresh_partners(partner_ids)
            return
        self.env.cr.commit()
        for attempt in range(5):
            try:
                engine.refresh_partners(partner_ids)
                self.env.cr.commit()
                return
            except psycopg2.errors.SerializationFailure:
                self.env.cr.rollback()
                time.sleep(1 + 2 * attempt)
        _logger.warning('fastmag: statistiques de %s client(s) non recalculées (accès concurrent) : '
                        'mises à jour au recalcul complet de la nuit.', len(partner_ids))

    @api.model
    def _cron_yr_pos_orders(self):
        """Background job: the imported tickets become POS orders, by batches (resumes where it stopped)."""
        start = time.monotonic()
        while True:
            _count, more = self._yr_make_pos_orders()
            if self._yr_can_commit():
                self.env.cr.commit()
            if not more:
                self.env['loyalty.motif'].sudo()._infer_campaigns()      # campaign results need the POS orders
                return
            if time.monotonic() - start > 240:
                self.env.ref('yr_data_migration.ir_cron_yr_fastmag_pos_orders')._trigger()
                return

    @api.model
    def _yr_trigger_pos_orders(self):
        cron = self.env.ref('yr_data_migration.ir_cron_yr_fastmag_pos_orders', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

    @api.model
    def _yr_delete_pos_orders(self, tickets=None):
        """Removes the POS orders made from fastmag tickets (all, or those of the given « shop/ticket » keys):
        they are made again from the imported lines."""
        cr = self.env.cr
        self.env['pos.order'].flush_model()
        self._yr_fk_indexes()                 # modules installed since: their columns are indexed too
        count = 0
        while True:
            if tickets is None:
                cr.execute('SELECT id FROM pos_order WHERE yr_fastmag_ticket IS NOT NULL LIMIT 20000')
            else:
                cr.execute(SQL('SELECT id FROM pos_order WHERE yr_fastmag_ticket = ANY(%s)', list(tickets)))
            ids = [row[0] for row in cr.fetchall()]
            if not ids:
                break
            cr.execute(SQL('UPDATE yr_legacy_sale_line SET pos_order_id = NULL WHERE pos_order_id = ANY(%s)', ids))
            cr.execute(SQL('DELETE FROM pos_order WHERE id = ANY(%s)', ids))
            count += len(ids)
            if tickets is not None:
                break
            if self._yr_can_commit():
                cr.commit()
        if tickets is None:
            cr.execute("""
                DELETE FROM pos_session s WHERE s.yr_fastmag
                   AND NOT EXISTS (SELECT 1 FROM pos_order o WHERE o.session_id = s.id)
            """)
        self.env['pos.order'].invalidate_model()
        self.env['pos.order.line'].invalidate_model()
        self.invalidate_model(['pos_order_id'])
        return count
