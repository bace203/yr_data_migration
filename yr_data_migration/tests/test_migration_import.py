# -*- coding: utf-8 -*-
"""Import of files shaped like the real fastmag exports (made-up people and articles)."""
import base64
import io
from datetime import date, datetime, timedelta

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import xlsxwriter

ARTICLE_HEADER = ['site', 'réf article', 'EAN bar', None, 'catégor', 'Désignation', 'bu', 'marque', 'ligne', 'axe',
                  'sous axe', 'nature', None, 'Cont', 'Genre', None, 'statut', None, 'Prix', None, 'UN', None,
                  'Date creati', 'Fourn CODE', None, 'Fourn DES']
NEW_HEADER = ['CardNumbre', 'SurName', 'FirstName', 'ID', 'Adress', 'Street2', 'Street3', 'City', 'PostalCode',
              'Phone', 'Birthday', 'EntranceDate', 'CodeShop', 'CodeSeller', 'FirstPurchase', 'Mobile', 'Email',
              'Montant_TTC']
OLD_HEADER = ['compteur', 'numCliente', 'numClienteOLD', 'naissance', 'nom_x', 'prenom', 'patronyme', 'rue1', 'cp',
              'cp2', 'ville', 'villeAttache', 'CdB', 'NPAI', 'numVendeuse', 'dateExcel', 'dateExcel2', 'dateSup',
              'Seg1', 'Seg2', 'Seg3', 'Seg4', 'Segment', 'dateLastSegment', 'Tel2', 'CdB_H', 'CdB_date', 'SegLettre',
              'Rue2', 'Rue3', 'Champ1', 'sexe']
CA_HEADER = ['CodeMag', 'date', 'Client', 'Cartefidelite', 'Nom', 'Prenom', 'TOTALCA']


def xlsx(rows):
    out = io.BytesIO()
    workbook = xlsxwriter.Workbook(out, {'in_memory': True})
    sheet = workbook.add_worksheet('fastmag')
    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if isinstance(value, datetime):
                sheet.write_datetime(r, c, value, date_format)
            elif value is not None:
                sheet.write(r, c, value)
    workbook.close()
    return base64.b64encode(out.getvalue())


def article(code, ean, name, axe, sub_axe, price, status='Actif ', supplier=('YVES', 'Y.ROCHER')):
    row = [None] * len(ARTICLE_HEADER)
    row[0], row[1], row[2], row[4], row[5], row[6], row[7], row[8] = \
        'DIST', code, ean, 'CAFV', name, 'YVES ROCHER', 'YVES ROCHER', 'CN3'
    row[9], row[10], row[11], row[16], row[18], row[20], row[22] = \
        axe, sub_axe, 'CORRECTEUR', status, price, 'UN', '16/09/2019'
    row[23], row[25] = supplier
    return row


@tagged('post_install', '-at_install')
class TestMigrationImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.store = cls.env['loyalty.store'].create({'name': 'YR Youg', 'code': 'YOUG', 'store_type': 'store',
                                                     'yr_fastmag_code': 'YR_YOUG'})

    def _import(self, rows, filename='fichier.xlsx', **options):
        wizard = self.env['yr.migration.import'].create(dict({'file': xlsx(rows), 'filename': filename}, **options))
        wizard.action_import()
        return wizard

    # ── articles ─────────────────────────────────────────────────────────
    def test_articles(self):
        empty = [None] * len(ARTICLE_HEADER)
        rows = [ARTICLE_HEADER, empty,
                article('T100102200', '9990005911601', 'Correcteur stick Zéro Défaut', 'MAQUILLAGE TEST', 'TEINT TEST', 17.349),
                empty, empty,
                article('T100102201', '9990005915821', 'Correcteur teinte 2', 'MAQUILLAGE TEST', 'TEINT TEST', 17.349),
                empty,
                article('T100200500', '9990005500500', 'Crème riche', 'SOIN TEST', 'HYDRA TEST', 38,
                        status='Inactif')]
        wizard = self._import(rows)
        self.assertEqual(wizard.file_type, 'article')
        Template = self.env['product.template']
        stick = Template.search([('default_code', '=', 'T100102200')])
        self.assertEqual((stick.barcode, stick.name, stick.list_price), ('9990005911601',
                                                                         'Correcteur stick Zéro Défaut', 17.349))
        self.assertTrue(stick.is_storable and stick.available_in_pos)
        # the axes are the categories: MAQUILLAGE › TEINT
        self.assertEqual(stick.pos_categ_ids.name, 'TEINT TEST')
        self.assertEqual(stick.pos_categ_ids.parent_id.name, 'MAQUILLAGE TEST')
        self.assertEqual((stick.yr_axe_id.name, stick.yr_sub_axe_id.name), ('MAQUILLAGE TEST', 'TEINT TEST'))
        self.assertTrue(stick.yr_axe_id.is_crm_family)
        self.assertEqual((stick.yr_category_code, stick.yr_line, stick.yr_status), ('CAFV', 'CN3', 'Actif'))
        self.assertEqual(stick.yr_create_date_legacy, date(2019, 9, 16))
        self.assertEqual(stick.seller_ids.partner_id.name, 'Y.ROCHER')
        self.assertEqual(stick.seller_ids.partner_id.ref, 'YVES')
        self.assertEqual(Template.search_count([('yr_sub_axe_id.name', '=', 'TEINT TEST')]), 2)
        self.assertEqual(self.env['pos.category'].search_count([('name', '=', 'TEINT TEST')]), 1)
        self.assertIn('Créés : <b>3</b>', wizard.result)
        # re-import: updated, nothing duplicated, archived option
        rows[2] = article('T100102200', '9990005911601', 'Correcteur stick', 'MAQUILLAGE TEST', 'TEINT TEST', 18.5)
        wizard = self._import(rows, archive_inactive=True)
        self.assertEqual(Template.search_count([('default_code', '=', 'T100102200')]), 1)
        self.assertEqual((stick.name, stick.list_price), ('Correcteur stick', 18.5))
        self.assertEqual(len(stick.seller_ids), 1)
        self.assertFalse(Template.with_context(active_test=False).search(
            [('default_code', '=', 'T100200500')]).active)
        self.assertIn('Mis à jour : <b>3</b>', wizard.result)

    def test_article_barcode_conflict(self):
        rows = [ARTICLE_HEADER,
                article('TA1', '9990000000001', 'Un', 'CORPS TEST', 'DOUCHE TEST', 5),
                article('TA2', '9990000000001', 'Deux', 'CORPS TEST', 'DOUCHE TEST', 6)]
        wizard = self._import(rows)
        self.assertIn('déjà utilisé', wizard.result)
        second = self.env['product.template'].search([('default_code', '=', 'TA2')])
        self.assertTrue(second and not second.barcode)

    # ── customers ────────────────────────────────────────────────────────
    def _new_row(self, card, last, first, birthday, mobile=None, amount=None, shop=None, city='MANOUBA'):
        return [card, last, first, None, '4 RUE EL KAADINE', None, None, city, 1006, None, birthday,
                datetime(2017, 5, 11), shop, 68, datetime(2018, 3, 22), mobile, None, amount]

    def test_customers_new_file(self):
        rows = [NEW_HEADER,
                self._new_row(990065941, 'KSOURI', 'AMEL', datetime(1987, 5, 15), 98461465, 43.7, 'YR_YOUG'),
                self._new_row(990070668, 'BEN', 'AIED AMEL', '20/11/0000', 24379898, 43),
                self._new_row(990065894, 'BARKA', 'MAROUA', '00/01/0000', 55140540, 32, 'YR_INCONNU')]
        wizard = self._import(rows)
        self.assertEqual(wizard.file_type, 'client_new')
        Partner = self.env['res.partner']
        amel = Partner.search([('customer_code', '=', '990065941')])
        self.assertEqual(amel.name, 'KSOURI AMEL')
        self.assertEqual(amel.barcode, '990065941')                # the old card still works at the till
        self.assertTrue(amel.crm_is_customer)
        self.assertEqual((amel.birth_day, amel.birth_month, amel.birth_year), ('15', '5', '1987'))
        self.assertEqual((amel.mobile, amel.zip, amel.city), ('98461465', '1006', 'MANOUBA'))
        self.assertEqual(amel.crm_store_id, self.store)
        self.assertEqual((amel.yr_entry_date, amel.yr_first_purchase_legacy), (date(2017, 5, 11), date(2018, 3, 22)))
        self.assertEqual(amel.sudo().yr_legacy_amount, 43.7)
        self.assertEqual(amel.yr_seller_code, '68')
        ben = Partner.search([('customer_code', '=', '990070668')])
        self.assertEqual((ben.name, ben.birth_day, ben.birth_month, ben.birth_year),
                         ('BEN AIED AMEL', '20', '11', False))     # 0000: day and month only
        maroua = Partner.search([('customer_code', '=', '990065894')])
        self.assertFalse(maroua.birth_day)                          # 00/01/0000: no birthday
        self.assertIn('YR_INCONNU', wizard.result)
        # the frozen migration amount is kept on re-import, empty fields are completed
        rows[1] = self._new_row(990065941, 'KSOURI', 'AMEL', datetime(1987, 5, 15), 98461465, 999, 'YR_YOUG')
        rows[1][16] = 'amel@example.com'
        self._import(rows)
        self.assertEqual(Partner.search_count([('customer_code', '=', '990065941')]), 1)
        self.assertEqual(amel.sudo().yr_legacy_amount, 43.7)
        self.assertEqual(amel.email, 'amel@example.com')
        with self.assertRaises(UserError):
            amel.sudo().write({'yr_legacy_amount': 1})

    def test_customers_old_file(self):
        def old(card, birthday, last, first, tel, gender=None, npai=0):
            row = [None] * len(OLD_HEADER)
            row[0], row[1], row[3], row[4], row[5], row[7], row[8], row[10] = \
                1, card, birthday, last, first, '8 RUE AHMED', '2083', 'CITE LA GAZELLE'
            row[13], row[14], row[15], row[22], row[24], row[31] = npai, 31, datetime(2014, 12, 12), 'PA', tel, gender
            return row
        rows = [OLD_HEADER,
                old('990001529', datetime(2000, 1, 23), 'AMRI ', 'BASSIMA', '22.51.36.90', 'F', 1),
                old('990001552', datetime(1978, 3, 25), 'MOATEMRI', 'CHIRAZ', '71.23.45.67')]
        wizard = self._import(rows)
        self.assertEqual(wizard.file_type, 'client_old')
        Partner = self.env['res.partner']
        bassima = Partner.search([('customer_code', '=', '990001529')])
        self.assertEqual((bassima.name, bassima.mobile, bassima.phone), ('AMRI BASSIMA', '22513690', False))
        self.assertEqual((bassima.birth_day, bassima.birth_month, bassima.birth_year), ('23', '1', False))
        self.assertEqual((bassima.yr_gender, bassima.yr_npai, bassima.yr_legacy_segment), ('f', True, 'PA'))
        chiraz = Partner.search([('customer_code', '=', '990001552')])
        self.assertEqual((chiraz.birth_year, chiraz.phone), ('1978', '71234567'))
        # year 2000 kept when the option is off
        self.env['res.partner'].search([('customer_code', '=', '990001529')]).write(
            {'birth_day': False, 'birth_month': False})
        self._import(rows, year_2000_unknown=False)
        self.assertEqual(bassima.birth_year, '2000')

    def test_turnover_file(self):
        """The fastmag purchases count in Fidélité & CRM: status, dates, turnover, last store."""
        today = date.today()
        recent, older = today - timedelta(days=20), today - timedelta(days=300)
        rows = [CA_HEADER,
                ['YR_YOUG', datetime.combine(recent, datetime.min.time()), 6, 990025739, 'FERCHICHI', 'SAMEH', 246.3],
                ['YR_AZUR', datetime.combine(older, datetime.min.time()), 6, 990025739, 'FERCHICHI', 'SAMEH', 1328.8],
                ['YR_MANAR', datetime(2026, 3, 19), 29, 999999999, 'INCONNUE', 'X', 21.8]]
        # history first: kept until the customer exists
        wizard = self._import(rows)
        self.assertEqual(wizard.file_type, 'client_ca')
        self.assertIn('Cartes sans fiche client : <b>2</b>', wizard.result)
        self.assertIn('YR_AZUR', wizard.result)                  # store codes to map
        Legacy = self.env['yr.legacy.purchase']
        self.assertEqual(Legacy.search_count([('card', '=', '990025739')]), 2)
        self._import([NEW_HEADER, self._new_row(990025739, 'FERCHICHI', 'SAMEH', datetime(1990, 1, 2))])
        sameh = self.env['res.partner'].search([('customer_code', '=', '990025739')])
        self.assertEqual(len(sameh.yr_legacy_purchase_ids), 2)
        self.assertAlmostEqual(sameh.crm_amount_total, 1575.1)
        self.assertEqual(sameh.crm_order_count, 2)
        self.assertEqual(sameh.crm_first_order_date, date(2018, 3, 22))   # first purchase of the customer file
        self.assertEqual(sameh.crm_last_order_date, recent)
        self.assertEqual(sameh.crm_last_store_id, self.store)
        self.assertEqual(sameh.crm_lifecycle, 'active')
        orders = self.env['loyalty.crm.order'].search([('partner_id', '=', sameh.id)])
        self.assertEqual(set(orders.mapped('source')), {'fastmag'})
        # re-import: amounts updated, no duplicate
        rows[1][6] = 250.0
        self._import(rows)
        self.assertEqual(Legacy.search_count([('card', '=', '990025739')]), 2)
        self.assertAlmostEqual(sameh.crm_amount_total, 1578.8)

    def test_customer_without_history_status(self):
        self._import([NEW_HEADER, self._new_row(990000001, 'ANCIENNE', 'CLIENTE', datetime(1980, 2, 3))])
        old = self.env['res.partner'].search([('customer_code', '=', '990000001')])
        self.assertEqual(old.crm_first_order_date, date(2018, 3, 22))
        self.assertEqual(old.crm_lifecycle, 'long_inactive')            # bought, long ago: not a prospect

    def test_unknown_file(self):
        wizard = self.env['yr.migration.import'].create({'file': xlsx([['a', 'b'], [1, 2]]), 'filename': 'x.xlsx'})
        self.assertFalse(wizard.file_type)
        with self.assertRaises(UserError):
            wizard.action_import()
