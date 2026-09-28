# -*- coding: utf-8 -*-
"""Import of the fastmag files (articles, customers 2017-2026, customers of the old system, 2-year turnover).

One screen: the kind of file is recognised from its header row. Re-importing a file updates the records it
created (matched on article code / barcode and customer card number) instead of duplicating them.
"""
import base64
import csv
import io
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools import html_escape

BATCH = 500
FILE_TYPES = [
    ('article', 'Articles (fiche article fastmag)'),
    ('client_new', 'Clients 2017-2026 (CardNumbre…)'),
    ('client_old', 'Clients ancien système (numCliente…)'),
    ('client_ca', 'CA clients (2 dernières années)'),
    ('sales_detail', 'Détail des ventes (ticket, utilisateur, vendeur)'),
    ('stores', 'Liste des magasins (magasin, code)'),
]
# columns of each file (normalised header → key); the first ones identify the file
COLUMNS = {
    'article': {
        'refarticle': 'code', 'eanbar': 'barcode', 'site': 'site', 'categor': 'category', 'categorie': 'category',
        'designation': 'name', 'marque': 'brand', 'ligne': 'line', 'axe': 'axe', 'sousaxe': 'sub_axe',
        'nature': 'nature', 'cont': 'packaging', 'genre': 'gender', 'statut': 'status', 'prix': 'price',
        'un': 'uom', 'datecreati': 'create_date', 'datecreation': 'create_date', 'fourncode': 'supplier_code',
        'fourndes': 'supplier_name',
    },
    'client_new': {
        'cardnumbre': 'card', 'cardnumber': 'card', 'surname': 'lastname', 'firstname': 'firstname', 'id': 'fm_id',
        'adress': 'street', 'address': 'street', 'street2': 'street2', 'street3': 'street3', 'city': 'city',
        'postalcode': 'zip', 'phone': 'phone', 'birthday': 'birthday', 'entrancedate': 'entry_date',
        'codeshop': 'shop', 'codeseller': 'seller', 'firstpurchase': 'first_purchase', 'mobile': 'mobile',
        'email': 'email', 'montantttc': 'amount',
    },
    'client_old': {
        'numcliente': 'card', 'numclienteold': 'old_code', 'naissance': 'birthday', 'nomx': 'lastname',
        'nom': 'lastname', 'prenom': 'firstname', 'rue1': 'street', 'rue2': 'street2', 'rue3': 'street3',
        'cp': 'zip', 'ville': 'city', 'npai': 'npai', 'numvendeuse': 'seller', 'segment': 'segment',
        'tel2': 'phone', 'sexe': 'gender', 'dateexcel': 'entry_date',
    },
    'client_ca': {
        'cartefidelite': 'card', 'totalca': 'amount', 'codemag': 'shop', 'date': 'date', 'client': 'fm_id',
        'nom': 'lastname', 'prenom': 'firstname',
    },
    'sales_detail': {
        'codemag': 'shop', 'vente': 'ticket', 'date': 'date', 'utilisateur': 'cashier', 'vendeur': 'seller',
        'client': 'fm_id', 'cartefidelite': 'card', 'nom': 'lastname', 'prenom': 'firstname', 'barcode': 'ref',
        'gencod': 'ean', 'reffournisseur': 'supplier_ref', 'designation': 'name', 'axe': 'axe', 'lignes': 'line',
        'quantite': 'qty', 'prix': 'price', 'remise': 'discount', 'total': 'total', 'motif': 'reason',
        'commentaire': 'comment',
    },
    'stores': {'magasin': 'name', 'nommagasin': 'name', 'code': 'code', 'codemagasin': 'code'},
}
SIGNATURE = {
    'article': {'refarticle', 'eanbar'},
    'client_new': {'cardnumbre'},
    'client_old': {'numcliente'},
    'client_ca': {'cartefidelite', 'totalca'},
    'sales_detail': {'vente', 'utilisateur', 'vendeur'},
    'stores': {'magasin', 'code'},
}
STAMP_REFS = {'DTT', 'TIMBRE'}      # « droit de timbre sur ticket »: not an article


class StoreIndex(dict):
    """fastmag shop code → store. Unknown « YR_AZUR » codes are matched on the store name (AZUR, YOUG → YOUGOSLAVIE)
    when only one store fits, and the code is then saved on the store (« Code magasin fastmag »)."""

    def __init__(self, stores):
        super().__init__()
        self.records = stores
        for store in stores:
            for code in filter(None, [store.code] + (store.yr_fastmag_code or '').split(',')):
                self[code.strip().upper()] = store

    def _resolve(self, code):
        code = (code or '').strip().upper()
        if not code:
            return None
        if dict.__contains__(self, code):
            return dict.__getitem__(self, code)
        key = norm(re.sub(r'^YR[_\s-]*', '', code, flags=re.I))
        found = self.records.browse()
        if key:
            found = self.records.filtered(lambda s: norm(s.code) == key) or \
                self.records.filtered(lambda s: norm(s.name) == key) or \
                self.records.filtered(lambda s: norm(s.name).startswith(key))
        if len(found) != 1:
            self[code] = None
            return None
        found.sudo().yr_fastmag_code = ','.join(filter(None, [found.yr_fastmag_code, code]))
        self[code] = found
        return found

    def get(self, code, default=None):
        return self._resolve(code) or default

    def __contains__(self, code):
        return bool(self._resolve(code))

    def __getitem__(self, code):
        store = self._resolve(code)
        if not store:
            raise KeyError(code)
        return store


def norm(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode()
    return ''.join(c for c in text.lower() if c.isalnum())


def text(value):
    """Cell → clean string (1006.0 → '1006', 104065941 → '104065941')."""
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, (datetime, date)):
        return value.strftime('%d/%m/%Y')
    return ' '.join(str(value).split())


def number(value):
    if value in (None, ''):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(' ', '').replace(',', '.'))
    except ValueError:
        return None


def parse_date(value):
    """datetime / 'jj/mm/aaaa' / 'aaaa-mm-jj' → date, None if empty or not a real date (00/01/0000)."""
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_birthday(value, unknown_years=()):
    """→ (day, month, year or None). '20/11/0000' = day and month only; '00/01/0000' = nothing."""
    if value in (None, ''):
        return None
    if isinstance(value, (datetime, date)):
        day, month, year = value.day, value.month, value.year
    else:
        match = re.match(r'^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{1,4})', str(value))
        if not match:
            return None
        day, month, year = (int(g) for g in match.groups())
    try:
        date(2000, month, day)          # leap year: 29/02 accepted
    except ValueError:
        return None
    if year in unknown_years or not 1900 <= year <= date.today().year - 5:
        year = None
    return day, month, year


def phone(value):
    digits = re.sub(r'\D', '', text(value))
    return digits or ''


class YrMigrationImport(models.TransientModel):
    _name = 'yr.migration.import'
    _description = 'Import fastmag'

    file = fields.Binary('Fichier Excel ou CSV', required=True)
    filename = fields.Char()
    file_type = fields.Selection(FILE_TYPES, 'Type de fichier', compute='_compute_file_type', store=True,
                                 readonly=False, help='Reconnu automatiquement d\'après les en-têtes.')
    # articles
    create_categories = fields.Boolean('Créer les catégories PdV manquantes (axe › sous-axe)', default=True)
    archive_inactive = fields.Boolean('Archiver les articles au statut autre que « Actif »', default=False)
    update_prices = fields.Boolean('Mettre à jour les prix des articles existants', default=True)
    # customers
    year_2000_unknown = fields.Boolean(
        'Année 2000 = année inconnue (fichier ancien système)', default=True,
        help='Dans l\'ancien système, beaucoup de dates de naissance ont l\'année 2000 par défaut : seuls le '
             'jour et le mois sont alors repris.')
    update_existing = fields.Boolean('Compléter les clients existants', default=True,
                                     help='Les champs vides de la fiche sont complétés ; rien n\'est effacé.')
    # sales detail
    create_sellers = fields.Boolean(
        'Créer les vendeurs manquants (Employés)', default=True,
        help='Chaque vendeur du fichier devient un employé, proposé ensuite dans la liste des vendeurs en caisse. '
             'Les utilisateurs (caissiers) sont seulement rattachés aux employés existants.')
    update_purchases = fields.Boolean(
        'Alimenter l\'historique d\'achats des clients', default=True,
        help='Total par carte, jour et magasin, comme le fichier « CA clients » (sans doublon avec lui) : '
             'statut client, CA, segments de Fidélité & CRM.')
    state = fields.Selection([('draft', 'draft'), ('done', 'done')], default='draft')
    result = fields.Html('Résultat', readonly=True)

    # ── reading ──────────────────────────────────────────────────────────
    def _rows(self, raw=False):
        """Header (normalised, or as is with raw=True) + data rows, empty rows skipped."""
        content = base64.b64decode(self.file or b'')
        name = (self.filename or '').lower()
        if name.endswith(('.xlsx', '.xlsm')) or content[:2] == b'PK':
            import openpyxl
            workbook = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            rows = workbook.active.iter_rows(values_only=True)
        else:
            decoded = ''
            for encoding in ('utf-8-sig', 'cp1252', 'latin-1'):
                try:
                    decoded = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            delimiter = max([';', ',', '\t', '|'], key=decoded[:4096].count)
            rows = csv.reader(io.StringIO(decoded), delimiter=delimiter)
        header = None
        for row in rows:
            if not any(c not in (None, '') and str(c).strip() for c in row):
                continue
            if header is None:
                header = [norm(c) for c in row]
                yield list(row) if raw else header
                continue
            yield list(row)
        if header is None:
            raise UserError(_('Le fichier est vide.'))

    @api.depends('file', 'filename')
    def _compute_file_type(self):
        for wizard in self:
            wizard.file_type = False
            if not wizard.file:
                continue
            try:
                header = set(next(wizard._rows()))
            except Exception:  # noqa: BLE001 - unreadable file: reported when importing
                continue
            wizard.file_type = next((kind for kind, keys in SIGNATURE.items() if keys <= header), False) or \
                ('stores' if wizard._is_store_list() else False)

    def _is_store_list(self):
        """A list without header row: store name, numeric code (« CARREFOUR | 2 »)."""
        try:
            first = [c for c in next(self._rows(raw=True)) if c not in (None, '')]
        except Exception:  # noqa: BLE001
            return False
        return len(first) == 2 and number(first[1]) is not None and number(first[0]) is None

    def _records(self, kind):
        rows = self._rows()
        header = next(rows)
        mapping = {}
        for idx, col in enumerate(header):
            key = COLUMNS[kind].get(col)
            if key and key not in mapping:
                mapping[key] = idx
        missing = [col for col in SIGNATURE[kind] if col not in header]
        if missing:
            raise UserError(_('Ce fichier n\'est pas un fichier « %s » : colonne(s) %s introuvable(s).',
                              dict(FILE_TYPES)[kind], ', '.join(missing)))
        for line_no, row in enumerate(rows, start=2):
            item = {key: (row[idx] if idx < len(row) else None) for key, idx in mapping.items()}
            item['_line'] = line_no
            yield item

    # ── entry point ──────────────────────────────────────────────────────
    def action_import(self):
        self.ensure_one()
        if not self.file_type:
            raise UserError(_('Type de fichier non reconnu : choisissez-le dans la liste.'))
        stats = defaultdict(int)
        errors = []
        env = self.with_context(tracking_disable=True, mail_create_nolog=True, mail_notrack=True,
                                yr_migration_force=True)
        getattr(env, '_import_%s' % self.file_type)(stats, errors)
        self.write({'state': 'done', 'result': self._render(stats, errors)})
        return {'type': 'ir.actions.act_window', 'res_model': self._name, 'res_id': self.id, 'view_mode': 'form',
                'target': 'new'}

    def _render(self, stats, errors):
        labels = {
            'rows': _('Lignes lues'), 'created': _('Créés'), 'updated': _('Mis à jour'), 'skipped': _('Ignorés'),
            'categories': _('Catégories PdV créées'), 'suppliers': _('Fournisseurs créés'),
            'archived': _('Articles archivés'), 'unknown_cards': _('Cartes sans fiche client'),
            'unknown_stores': _('Lignes avec magasin inconnu'), 'customers': _('Clients avec historique'),
            'tickets': _('Tickets'), 'purchases': _('Achats clients (historique CRM)'),
            'employees': _('Vendeurs créés (Employés)'), 'unknown_products': _('Lignes sans article connu'),
        }
        html = '<p><b>%s</b></p><ul>' % html_escape(dict(FILE_TYPES)[self.file_type])
        for key, label in labels.items():
            if stats.get(key):
                html += '<li>%s : <b>%s</b></li>' % (html_escape(label), stats[key])
        html += '</ul>'
        if stats.get('stores_missing'):
            html += '<p class="text-warning">%s %s</p>' % (
                html_escape(_('Codes magasin à renseigner dans Fidélité & CRM › Configuration › Magasins '
                              '(champ « Code magasin fastmag ») puis réimporter :')),
                html_escape(', '.join(sorted(stats['stores_missing']))))
        if errors:
            html += '<p class="text-danger"><b>%s</b></p><ul>' % html_escape(_('%s ligne(s) en erreur', len(errors)))
            for line, code, message in errors[:200]:
                html += '<li>%s %s — %s : %s</li>' % (html_escape(_('Ligne')), line, html_escape(code or ''),
                                                       html_escape(message))
            html += '</ul>'
        return html

    # ── articles ─────────────────────────────────────────────────────────
    def _pos_category(self, name, parent, cache, stats):
        name = text(name)
        if not name:
            return self.env['pos.category']
        key = (name.upper(), parent.id)
        if key not in cache:
            Category = self.env['pos.category']
            categ = Category.search([('name', '=ilike', name), ('parent_id', '=', parent.id or False)], limit=1)
            if not categ and self.create_categories:
                categ = Category.create({'name': name, 'parent_id': parent.id or False,
                                         'is_crm_family': not parent, 'import_code': name.upper()})
                stats['categories'] += 1
            cache[key] = categ
        return cache[key]

    def _supplier(self, code, name, cache, stats):
        code, name = text(code), text(name)
        if not code and not name:
            return self.env['res.partner']
        key = code or name
        if key not in cache:
            Partner = self.env['res.partner'].with_context(crm_no_card=True)
            supplier = Partner.search([('ref', '=', code), ('is_company', '=', True)], limit=1) if code else Partner
            if not supplier and name:
                supplier = Partner.search([('name', '=ilike', name), ('is_company', '=', True)], limit=1)
            if not supplier:
                supplier = Partner.create({'name': name or code, 'ref': code or False, 'is_company': True,
                                           'crm_is_customer': False, 'supplier_rank': 1})
                stats['suppliers'] += 1
            cache[key] = supplier
        return cache[key]

    def _import_article(self, stats, errors):
        items = [i for i in self._records('article') if text(i.get('code')) or text(i.get('barcode'))]
        stats['rows'] = len(items)
        Template = self.env['product.template'].with_context(active_test=False)
        codes = [text(i.get('code')) for i in items if text(i.get('code'))]
        barcodes = [text(i.get('barcode')) for i in items if text(i.get('barcode'))]
        by_code, by_barcode = {}, {}
        for chunk in range(0, max(len(codes), len(barcodes)), 5000):
            for tmpl in Template.search(['|', ('default_code', 'in', codes[chunk:chunk + 5000]),
                                         ('barcode', 'in', barcodes[chunk:chunk + 5000])]):
                by_code.setdefault(tmpl.default_code, tmpl)
                by_barcode.setdefault(tmpl.barcode, tmpl)
        categ_cache, supplier_cache = {}, {}
        unit = self.env.ref('uom.product_uom_unit')
        seen_barcodes = set()
        to_create = []
        for item in items:
            code, barcode = text(item.get('code')), text(item.get('barcode'))
            owner = by_barcode.get(barcode) if barcode else None
            # a line with a reference matches on it: two fastmag references may share a barcode
            if code:
                tmpl = by_code.get(code)
                if not tmpl and owner and owner is not True and not owner.default_code:
                    tmpl = owner                       # article created before without reference
            else:
                tmpl = owner
            if barcode and (barcode in seen_barcodes or (by_barcode.get(barcode) and by_barcode[barcode] != tmpl)):
                errors.append((item['_line'], code, _('code-barres %s déjà utilisé par un autre article : '
                                                     'article repris sans code-barres', barcode)))
                barcode = ''
            if barcode:
                seen_barcodes.add(barcode)
            axe = self._pos_category(item.get('axe'), self.env['pos.category'], categ_cache, stats)
            sub_axe = self._pos_category(item.get('sub_axe'), axe, categ_cache, stats) if axe else axe
            price = number(item.get('price'))
            status = text(item.get('status'))
            vals = {
                'yr_site': text(item.get('site')) or False,
                'yr_category_code': text(item.get('category')) or False,
                'yr_brand': text(item.get('brand')) or False,
                'yr_line': text(item.get('line')) or False,
                'yr_axe_id': axe.id or False,
                'yr_sub_axe_id': sub_axe.id or False,
                'yr_nature': text(item.get('nature')) or False,
                'yr_packaging': text(item.get('packaging')) or False,
                'yr_gender': text(item.get('gender')) or False,
                'yr_status': status or False,
                'yr_create_date_legacy': parse_date(item.get('create_date')) or False,
                'yr_supplier_code': text(item.get('supplier_code')) or False,
            }
            if sub_axe or axe:
                vals['pos_categ_ids'] = [(6, 0, (sub_axe or axe).ids)]
            if self.archive_inactive and status:
                vals['active'] = status.lower().startswith('actif')
                if not vals['active']:
                    stats['archived'] += 1
            supplier = self._supplier(item.get('supplier_code'), item.get('supplier_name'), supplier_cache, stats)
            if tmpl is True:          # same reference twice in the file: first line wins
                stats['skipped'] += 1
                continue
            if tmpl:
                if code and not tmpl.default_code:
                    vals['default_code'] = code
                if barcode and not tmpl.barcode:
                    vals['barcode'] = barcode
                if price is not None and self.update_prices:
                    vals['list_price'] = price
                if text(item.get('name')):
                    vals['name'] = text(item.get('name'))
                tmpl.write(vals)
                if supplier and supplier not in tmpl.seller_ids.partner_id:
                    tmpl.seller_ids = [(0, 0, {'partner_id': supplier.id})]
                stats['updated'] += 1
            else:
                vals.update({
                    'name': text(item.get('name')) or code or barcode, 'default_code': code or False,
                    'barcode': barcode or False, 'list_price': price or 0.0, 'type': 'consu',
                    'is_storable': True, 'available_in_pos': True, 'sale_ok': True,
                    'uom_id': unit.id, 'uom_po_id': unit.id,
                })
                if supplier:
                    vals['seller_ids'] = [(0, 0, {'partner_id': supplier.id})]
                to_create.append(vals)
                if code:
                    by_code[code] = True       # same code twice in the file: created once
            if len(to_create) >= BATCH:
                stats['created'] += len(Template.create(to_create))
                to_create = []
        if to_create:
            stats['created'] += len(Template.create(to_create))

    # ── customers ────────────────────────────────────────────────────────
    def _stores(self):
        return StoreIndex(self.env['loyalty.store'].search([]))

    def _existing_customers(self, cards):
        Partner = self.env['res.partner'].with_context(active_test=False)
        found = {}
        for chunk in range(0, len(cards), 5000):
            part = cards[chunk:chunk + 5000]
            for partner in Partner.search(['|', ('customer_code', 'in', part), ('yr_legacy_code', 'in', part)]):
                found.setdefault(partner.customer_code, partner)
                found.setdefault(partner.yr_legacy_code, partner)
        return found

    def _customer_vals(self, item, kind, stores, stats):
        unknown_years = (2000,) if kind == 'client_old' and self.year_2000_unknown else ()
        name = ' '.join(filter(None, [text(item.get('lastname')), text(item.get('firstname'))]))
        street = ' '.join(filter(None, [text(item.get('street')), text(item.get('street2')),
                                        text(item.get('street3'))]))
        vals = {
            'name': name, 'street': street, 'city': text(item.get('city')), 'zip': text(item.get('zip')),
            'email': text(item.get('email')).lower(), 'yr_seller_code': text(item.get('seller')),
            'yr_legacy_old_code': text(item.get('old_code')), 'yr_legacy_segment': text(item.get('segment')),
            'yr_entry_date': parse_date(item.get('entry_date')),
            'yr_first_purchase_legacy': parse_date(item.get('first_purchase')),
        }
        tel, mobile = phone(item.get('phone')), phone(item.get('mobile'))
        if kind == 'client_old' and tel and tel[:1] in '2459' and len(tel) == 8:
            mobile, tel = tel, ''            # Tunisian mobile numbers start with 2, 4, 5 or 9
        vals.update(phone=tel, mobile=mobile)
        gender = text(item.get('gender')).lower()
        vals['yr_gender'] = 'f' if gender[:1] == 'f' else 'h' if gender[:1] in ('h', 'm') else False
        if kind == 'client_old' and item.get('npai') not in (None, ''):
            vals['yr_npai'] = bool(number(item.get('npai')))
        birthday = parse_birthday(item.get('birthday'), unknown_years)
        if birthday:
            day, month, year = birthday
            vals.update(birth_day=str(day), birth_month=str(month), birth_year=str(year) if year else False)
        amount = number(item.get('amount'))
        if amount:
            vals.update(yr_legacy_amount=amount, yr_migration_date=fields.Date.context_today(self))
        shop = text(item.get('shop')).upper()
        if shop:
            if shop in stores:
                vals['crm_store_id'] = stores[shop].id
            else:
                stats['stores_missing'] = stats.get('stores_missing') or set()
                stats['stores_missing'].add(shop)
                stats['unknown_stores'] += 1
        return {k: v for k, v in vals.items() if v not in (None, '', False) or k == 'birth_year'}

    def _import_customers(self, kind, stats, errors):
        items = [i for i in self._records(kind) if text(i.get('card'))]
        stats['rows'] = len(items)
        stores = self._stores()
        existing = self._existing_customers(list({text(i['card']) for i in items}))
        Partner = self.env['res.partner'].sudo()
        to_create, created_cards = [], set()
        for item in items:
            card = text(item['card'])
            vals = self._customer_vals(item, kind, stores, stats)
            if not vals.get('birth_day'):
                vals.pop('birth_year', None)
            partner = existing.get(card)
            if partner:
                if not self.update_existing:
                    stats['skipped'] += 1
                    continue
                # complete the empty fields only; the frozen migration amount is never replaced
                update = {k: v for k, v in vals.items() if not partner.sudo()[k] and k != 'birth_year'}
                if 'birth_day' in update and vals.get('birth_year'):
                    update['birth_year'] = vals['birth_year']
                if 'birth_day' in update and 'birth_month' not in update:
                    update.pop('birth_day')
                if not partner.yr_legacy_code:
                    update['yr_legacy_code'] = card
                if update:
                    try:
                        with self.env.cr.savepoint():
                            partner.sudo().write(update)
                        stats['updated'] += 1
                    except Exception as error:  # noqa: BLE001 - reported per line
                        errors.append((item['_line'], card, str(error)))
                else:
                    stats['skipped'] += 1
                continue
            if card in created_cards:
                errors.append((item['_line'], card, _('numéro de carte en double dans le fichier : ligne ignorée')))
                continue
            vals.update({
                'name': vals.get('name') or _('Client %s', card), 'customer_code': card, 'barcode': card,
                'yr_legacy_code': card, 'crm_is_customer': True, 'customer_rank': 1,
            })
            to_create.append((item['_line'], vals))
            created_cards.add(card)
            if len(to_create) >= BATCH:
                self._create_customers(Partner, to_create, stats, errors)
                to_create = []
        if to_create:
            self._create_customers(Partner, to_create, stats, errors)
        cards = list({text(i['card']) for i in items})
        partner_ids = {partner.id for partner in self._existing_customers(cards).values()}
        partner_ids |= self.env['yr.legacy.purchase']._link_partners(cards)
        self._refresh_crm(partner_ids)

    def _create_customers(self, Partner, batch, stats, errors):
        try:
            with self.env.cr.savepoint():
                Partner.create([vals for _line, vals in batch])
            stats['created'] += len(batch)
        except Exception:  # noqa: BLE001 - one bad line: retry one by one to report it
            for line, vals in batch:
                try:
                    with self.env.cr.savepoint():
                        Partner.create(vals)
                    stats['created'] += 1
                except Exception as error:  # noqa: BLE001
                    errors.append((line, vals.get('customer_code'), str(error).split('\n')[0]))

    def _import_client_new(self, stats, errors):
        self._import_customers('client_new', stats, errors)

    def _import_client_old(self, stats, errors):
        self._import_customers('client_old', stats, errors)

    # ── 2-year turnover per customer: purchase history ───────────────────
    def _import_client_ca(self, stats, errors):
        """One fastmag purchase per card, day and store; re-importing updates the amounts."""
        visits = {}
        for item in self._records('client_ca'):
            card, day = text(item.get('card')), parse_date(item.get('date'))
            if not card or not day:
                if card:
                    errors.append((item['_line'], card, _('date absente ou invalide')))
                continue
            stats['rows'] += 1
            key = (card, datetime.combine(day, datetime.min.time()).replace(hour=12), text(item.get('shop')).upper())
            visit = visits.setdefault(key, {'amount': 0.0, 'client': text(item.get('fm_id'))})
            visit['amount'] += number(item.get('amount')) or 0.0
        self._save_purchases(visits, stats, errors)

    def _save_purchases(self, visits, stats, errors, created='created', updated='updated', stores=None):
        """visits: {(card, datetime at noon, shop): {'amount', 'client'}} → yr.legacy.purchase (upsert)."""
        stores = stores if stores is not None else self._stores()
        unknown_shops = {shop for _card, _day, shop in visits if shop and shop not in stores}
        if unknown_shops:
            stats['stores_missing'] = unknown_shops
        Legacy = self.env['yr.legacy.purchase'].sudo()
        cards = list({card for card, _day, _shop in visits})
        existing = {}
        for chunk in range(0, len(cards), 5000):
            for line in Legacy.search([('card', 'in', cards[chunk:chunk + 5000])]):
                existing[(line.card, line.date, line.shop_code or '')] = line
        to_create = []
        for (card, day, shop), visit in visits.items():
            store = stores.get(shop) if shop else False
            line = existing.get((card, day, shop))
            if line:
                vals = {}
                if abs(line.amount - visit['amount']) > 0.0001:
                    vals['amount'] = visit['amount']
                if store and line.store_id != store:
                    vals['store_id'] = store.id
                if vals:
                    line.write(vals)
                    stats[updated] += 1
                continue
            if shop and not store:
                stats['unknown_stores'] += 1
            to_create.append({
                'card': card, 'date': day, 'shop_code': shop or False, 'store_id': store.id if store else False,
                'company_id': (store.company_id if store else self.env.company).id, 'amount': visit['amount'],
                'legacy_client_id': visit['client'] or False,
            })
            if len(to_create) >= 5000:
                stats[created] += len(Legacy.create(to_create))
                to_create = []
        if to_create:
            stats[created] += len(Legacy.create(to_create))
        Legacy._link_partners(cards)
        partner_ids = set()
        for chunk in range(0, len(cards), 5000):
            partner_ids |= set(Legacy.search([('card', 'in', cards[chunk:chunk + 5000]),
                                              ('partner_id', '!=', False)]).partner_id.ids)
        self._refresh_crm(partner_ids)
        stats['customers'] = len(set(Legacy.search([('card', 'in', cards), ('partner_id', '!=', False)])
                                     .mapped('partner_id').ids))
        unknown = len(set(Legacy.search([('card', 'in', cards), ('partner_id', '=', False)]).mapped('card')))
        if unknown:
            stats['unknown_cards'] = unknown
            errors.append(('-', '', _('%s carte(s) sans fiche client pour l\'instant : leurs achats sont gardés et '
                                      'seront rattachés à l\'import des fichiers clients.', unknown)))

    # ── store list: magasin, code ────────────────────────────────────────
    def _import_stores(self, stats, errors):
        """Creates the missing stores, sets the code of the others (matched on code, then on name)."""
        rows = self._rows(raw=True)
        first = next(rows)
        header = [norm(c) for c in first]
        if {'magasin', 'code'} <= set(header):
            name_idx, code_idx = header.index('magasin'), header.index('code')
        else:       # no header row: name, code
            name_idx, code_idx = 0, 1
            rows = iter([first] + list(rows))
        Store = self.env['loyalty.store'].with_context(active_test=False)
        stores = Store.search([])
        for line_no, row in enumerate(rows, start=2):
            row = list(row) + [None, None]
            name, code = text(row[name_idx]), text(row[code_idx])
            if not name or not code:
                if name or code:
                    errors.append((line_no, name or code, _('nom du magasin ou code manquant')))
                continue
            stats['rows'] += 1
            store = stores.filtered(lambda s: (s.code or '').strip().upper() == code.upper()) or \
                stores.filtered(lambda s: norm(s.name) == norm(name))
            if len(store) > 1:
                errors.append((line_no, name, _('plusieurs magasins correspondent : %s',
                                                ', '.join(store.mapped('name')))))
                continue
            if store:
                vals = {}
                if store.code != code:
                    # the former code stays known for the files that still use it
                    vals['code'] = code
                    vals['yr_fastmag_code'] = ','.join(filter(None, [store.yr_fastmag_code, store.code]))
                if not store.active:
                    vals['active'] = True
                if vals:
                    store.write(vals)
                    stats['updated'] += 1
                else:
                    stats['skipped'] += 1
                continue
            web = any(word in norm(name) for word in ('eshop', 'siteweb', 'website', 'ecommerce'))
            stores |= Store.create({'name': name, 'code': code, 'store_type': 'website' if web else 'store'})
            stats['created'] += 1

    # ── sales detail: one line per ticket line, cashier and seller ───────
    def _import_sales_detail(self, stats, errors):
        SaleLine = self.env['yr.legacy.sale.line'].sudo()
        stores = self._stores()
        employees = SaleLine._employee_index()
        Employee = self.env['hr.employee'].sudo()
        Product = self.env['product.product'].with_context(active_test=False)
        items, refs, eans, tickets, rank = [], set(), set(), set(), defaultdict(int)
        for item in self._records('sales_detail'):
            shop, ticket, day = text(item.get('shop')).upper(), text(item.get('ticket')), parse_date(item.get('date'))
            if not shop and not ticket:
                continue
            if not shop or not ticket or not day:
                errors.append((item['_line'], ticket, _('magasin, n° de vente ou date manquant')))
                continue
            stats['rows'] += 1
            rank[(shop, ticket)] += 1
            item.update(shop=shop, ticket=ticket, day=day, sequence=rank[(shop, ticket)])
            ref = text(item.get('ref'))
            item['stamp'] = ref.upper() in STAMP_REFS
            if not item['stamp']:
                refs.add(ref)
                eans.add(text(item.get('ean')))
            tickets.add((shop, ticket))
            items.append(item)
        stats['tickets'] = len(tickets)
        products = {}
        refs.discard('')
        eans.discard('')
        for product in Product.search(['|', ('default_code', 'in', list(refs)), ('barcode', 'in', list(eans))]):
            products.setdefault(('ref', product.default_code), product)
            products.setdefault(('ean', product.barcode), product)
        existing = {}
        shops = list({shop for shop, _ticket in tickets})
        for line in SaleLine.search([('shop_code', 'in', shops), ('ticket', 'in', list({t for _s, t in tickets}))]):
            existing[(line.shop_code, line.ticket, line.sequence)] = line

        def employee(name, create, store):
            key = ' '.join(name.upper().split())
            if not key:
                return False
            if key not in employees and create:
                employees[key] = Employee.create({
                    'name': name, 'company_id': (store.company_id if store else self.env.company).id})
                stats['employees'] += 1
            return employees.get(key, Employee).id or False

        visits, to_create, cards = {}, [], set()
        for item in items:
            store = stores.get(item['shop'])
            if not store:
                stats['stores_missing'] = stats.get('stores_missing') or set()
                stats['stores_missing'].add(item['shop'])
            card = text(item.get('card'))
            card = '' if card in ('0', '') else card
            ref, ean = text(item.get('ref')), text(item.get('ean'))
            product = False if item['stamp'] else products.get(('ref', ref)) or products.get(('ean', ean))
            if not item['stamp'] and not product:
                stats['unknown_products'] += 1
            total = number(item.get('total')) or 0.0
            cashier, seller = text(item.get('cashier')), text(item.get('seller'))
            vals = {
                'shop_code': item['shop'], 'store_id': store.id if store else False,
                'company_id': (store.company_id if store else self.env.company).id,
                'ticket': item['ticket'], 'sequence': item['sequence'], 'date': item['day'],
                'cashier_name': cashier or False, 'cashier_id': employee(cashier, False, store),
                'seller_name': seller or False, 'seller_id': employee(seller, self.create_sellers, store),
                'card': card or False, 'legacy_client_id': text(item.get('fm_id')) if card else False,
                'product_ref': ref or False, 'barcode': ean or False, 'product_id': product.id if product else False,
                'name': text(item.get('name')) or False, 'axe': text(item.get('axe')) or False,
                'product_line': text(item.get('line')) or False, 'is_stamp': item['stamp'],
                'qty': number(item.get('qty')) or 0.0, 'price_unit': number(item.get('price')) or 0.0,
                'discount': number(item.get('discount')) or 0.0, 'amount': total,
                'reason': text(item.get('reason')) or False, 'comment': text(item.get('comment')) or False,
            }
            line = existing.get((item['shop'], item['ticket'], item['sequence']))
            if line:
                line.write(vals)
                stats['updated'] += 1
            else:
                to_create.append(vals)
            if card:
                cards.add(card)
                key = (card, datetime.combine(item['day'], datetime.min.time()).replace(hour=12), item['shop'])
                visit = visits.setdefault(key, {'amount': 0.0, 'client': text(item.get('fm_id'))})
                visit['amount'] += total
            if len(to_create) >= 5000:
                stats['created'] += len(SaleLine.create(to_create))
                to_create = []
        if to_create:
            stats['created'] += len(SaleLine.create(to_create))
        SaleLine._link_partners(list(cards))
        if visits and self.update_purchases:
            self._save_purchases(visits, stats, errors, created='purchases', updated='purchases', stores=stores)

    def _refresh_crm(self, partner_ids):
        """Customer status, first / last purchase, turnover of Fidélité & CRM, now (normally hourly)."""
        if partner_ids:
            self.env['loyalty.crm.engine'].sudo().refresh_partners(list(partner_ids))
