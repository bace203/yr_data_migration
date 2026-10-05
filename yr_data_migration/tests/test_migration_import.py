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
DETAIL_HEADER = ['CodeMag', 'Vente', 'date', 'Utilisateur', 'Vendeur', 'Client', 'Cartefidelite', 'Nom', 'Prenom',
                 'Barcode', 'gencod', 'Reffournisseur', 'Designation', 'Axe', 'Lignes', 'Quantite', 'Prix', 'Remise',
                 'Total', 'Motif', 'Commentaire']


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


def xlsx_sheets(sheets):
    """{sheet name: rows} → one workbook with several sheets."""
    out = io.BytesIO()
    workbook = xlsxwriter.Workbook(out, {'in_memory': True})
    date_format = workbook.add_format({'num_format': 'dd/mm/yyyy'})
    for name, rows in sheets.items():
        sheet = workbook.add_worksheet(name)
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

    def test_articles_imported_before_by_crm_screen(self):
        """Articles already created by Fidélité & CRM › Import articles: completed, not duplicated."""
        rows = [ARTICLE_HEADER,
                article('T100191452', '9990005648712', 'Brillance vinaigre', 'CAPILLAIRE TEST', 'SOIN CHEVEUX', 12),
                article('T100191954', '9990005648712', 'Capillaire brillance', 'CAPILLAIRE TEST', 'SOIN CHEVEUX', 12)]
        # articles created before by the CRM import (without the fastmag fields)
        Template = self.env['product.template']
        Template.create([{'name': 'Brillance vinaigre', 'default_code': 'T100191452', 'barcode': '9990005648712',
                          'is_storable': True},
                         {'name': 'Capillaire brillance', 'default_code': 'T100191954', 'is_storable': True}])
        first = Template.search([('default_code', '=', 'T100191452')])
        second = Template.search([('default_code', '=', 'T100191954')])
        self.assertFalse(first.yr_line)
        wizard = self._import(rows)
        self.assertEqual(Template.search_count([('default_code', 'in', ['T100191452', 'T100191954'])]), 2)
        for tmpl in first | second:
            self.assertEqual((tmpl.yr_line, tmpl.yr_brand, tmpl.yr_status), ('CN3', 'YVES ROCHER', 'Actif'))
            self.assertEqual(tmpl.yr_sub_axe_id.name, 'SOIN CHEVEUX')
            self.assertEqual(tmpl.yr_axe_id.name, 'CAPILLAIRE TEST')
        self.assertEqual((first.barcode, second.barcode), ('9990005648712', False))
        self.assertIn('Mis à jour : <b>2</b>', wizard.result)

    def test_crm_import_screen_does_the_fastmag_import(self):
        rows = [ARTICLE_HEADER, article('T100102999', '9990005911999', 'Stick', 'MAQUILLAGE TEST', 'TEINT TEST', 9)]
        crm = self.env['loyalty.product.import'].create({'file': xlsx(rows)})       # no file name sent
        crm.action_import()
        tmpl = self.env['product.template'].search([('default_code', '=', 'T100102999')])
        self.assertEqual((tmpl.yr_line, tmpl.yr_sub_axe_id.name, tmpl.yr_brand), ('CN3', 'TEINT TEST', 'YVES ROCHER'))
        self.assertIn('Articles (fiche article fastmag)', crm.result)
        # an ordinary article file keeps the CRM import
        other = self.env['loyalty.product.import'].create({
            'file': base64.b64encode('Code article;Désignation;Prix\nTX1;Autre;3\n'.encode()), 'filename': 'a.csv'})
        other.action_import()
        self.assertTrue(self.env['product.template'].search([('default_code', '=', 'TX1')]))

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
                ['YR_XQZW', datetime.combine(older, datetime.min.time()), 6, 990025739, 'FERCHICHI', 'SAMEH', 1328.8],
                ['YR_MANAR', datetime(2026, 3, 19), 29, 999999999, 'INCONNUE', 'X', 21.8]]
        # history first: kept until the customer exists
        wizard = self._import(rows)
        self.assertEqual(wizard.file_type, 'client_ca')
        self.assertIn('Cartes sans fiche client : <b>2</b>', wizard.result)
        self.assertIn('YR_XQZW', wizard.result)                  # store codes to map
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

    # ── store list ───────────────────────────────────────────────────────
    def test_store_list(self):
        Store = self.env['loyalty.store']
        azur = Store.create({'name': 'Azurq', 'code': 'AZRQ'})
        wizard = self._import([['Magasin', 'Code'], ['AZURQ', 923], ['ZEPHYRQ TEST', 920], ['eshop', 926]])
        self.assertEqual(wizard.file_type, 'stores')
        self.assertEqual((azur.code, azur.yr_fastmag_code), ('923', 'AZRQ'))       # the former code stays known
        zephyr = Store.search([('code', '=', '920')])
        self.assertEqual((zephyr.name, zephyr.store_type), ('ZEPHYRQ TEST', 'store'))
        self.assertEqual(Store.search([('code', '=', '926')]).store_type, 'website')
        # again, and without header row: nothing duplicated
        wizard = self._import([['ZEPHYRQ TEST', 920], ['NABEUL TEST', 919]])
        self.assertEqual(wizard.file_type, 'stores')
        self.assertEqual(Store.search_count([('name', '=', 'ZEPHYRQ TEST')]), 1)
        self.assertTrue(Store.search([('code', '=', '919'), ('name', '=', 'NABEUL TEST')]))
        # « YR_ZEPHYR » of the fastmag files is recognised from the name, and remembered
        stores = self.env['yr.migration.import']._stores()
        self.assertEqual(stores.get('YR_ZEPHYRQ'), zephyr)
        self.assertIn('YR_ZEPHYRQ', zephyr.yr_fastmag_code)

    def test_workbook_stores_and_sellers(self):
        """The « vendeurs / magasins » workbook: Feuil1 sellers per store, Feuil2 magasin | YR_ code | number."""
        Store = self.env['loyalty.store']
        carr = Store.create({'name': 'CARREFOURQ', 'code': '992'})
        config = self.env['pos.config'].create({'name': 'Caisse Carrefourq', 'crm_store_id': carr.id})
        sellers = [['Code magasin ', 'Vendeurs', 'Code Logistique'],
                   ['YR_CARRQ', 'RIMQ', 801], [None, 'SANAQ TEST', 802],
                   ['YR_MALLSOUQ', 'IMENQ', 803], [None, 'SANAQ TEST', 804]]
        stores = [['Magasin ', 'Code -Magasin ', 'Num-Magasin '],
                  ['CARREFOURQ', 'YR_CARRQ', 992], ['MALL OF SOUSSEQ', 'YR_MALLSOUQ', 994]]
        wizard = self.env['yr.migration.import'].create({
            'file': xlsx_sheets({'Feuil1': sellers, 'Feuil2': stores}), 'filename': 'vendeurmagasin.xlsx'})
        self.assertEqual(wizard.file_type, 'workbook')
        wizard.action_import()
        self.assertIn('Feuil2', wizard.result)
        # stores: the YR_ code of the sales files is kept on the store, the number is its code
        self.assertIn('YR_CARRQ', carr.yr_fastmag_code)
        mall = Store.search([('code', '=', '994')])
        self.assertEqual((mall.name, mall.yr_fastmag_code), ('MALL OF SOUSSEQ', 'YR_MALLSOUQ'))
        self.assertEqual(self.env['yr.migration.import']._stores().get('YR_MALLSOUQ'), mall)
        # sellers: employees of their store, with the logistic code, proposed at the store's till
        Employee = self.env['hr.employee']
        rim = Employee.search([('yr_logistic_code', '=', '801')])
        self.assertEqual((rim.name, rim.yr_store_id), ('RIMQ', carr))
        self.assertIn(rim, config.yr_seller_employee_ids)
        self.assertEqual(Employee.search([('yr_logistic_code', '=', '803')]).yr_store_id, mall)  # code carried down
        # store codes with a typing error or abbreviated, and an unknown store (created)
        mahs = Store.create({'name': 'KAIROUANQZ', 'code': '995'})
        sfax = Store.create({'name': 'BIZERTEQ NORD', 'code': '996'})
        more = [['Code magasin ', 'Vendeurs', 'Code Logistique'],
                ['YR_KAYROUANQZ', 'HAMIDAQ', 811], ['YR_BNORD', 'OLFAQ', 812], ['YR_HBQ', 'NESRINEQ', 813]]
        self._import(more)
        self.assertEqual(Employee.search([('yr_logistic_code', '=', '811')]).yr_store_id, mahs)
        self.assertEqual(Employee.search([('yr_logistic_code', '=', '812')]).yr_store_id, sfax)
        hb = Employee.search([('yr_logistic_code', '=', '813')]).yr_store_id
        self.assertEqual((hb.name, hb.yr_fastmag_code), ('HBQ', 'YR_HBQ'))
        # same name, other logistic code: two different sellers
        self.assertEqual(len(Employee.search([('name', '=', 'SANAQ TEST')])), 2)
        # again: nothing duplicated
        wizard = self.env['yr.migration.import'].create({
            'file': xlsx_sheets({'Feuil1': sellers, 'Feuil2': stores}), 'filename': 'vendeurmagasin.xlsx'})
        wizard.action_import()
        self.assertEqual(Employee.search_count([('yr_logistic_code', 'in', ['801', '802', '803', '804'])]), 4)
        self.assertEqual(Store.search_count([('code', '=', '994')]), 1)

    def test_sales_detail_client_column(self):
        """Sales file « INES-YVESROCHER | CodeMag | … | Client | vente | … | PrixNet | total_1 | valeurArticle »:
        no card column, the client code is the card."""
        partner = self.env['res.partner'].create({'name': 'Cliente Y', 'customer_code': 'Y88074Q'})
        header = ['INES-YVESROCHER', 'CodeMag', 'Utilisateur', 'Vendeur', 'Date', 'Client', 'vente', 'Barcode',
                  'Quantite', 'Prix', 'remise', 'PrixNet', 'total', 'total_1', 'valeurArticle', 'motif']
        rows = [header,
                ['INES-YVESROCHER', 'YR_YOUG', 'RIM_T', 'SANAQ', '27/11/2017', 'Y88074Q', 2, 100102550, 1, 34, 0, 34,
                 34, 67, 16.73, None],
                ['INES-YVESROCHER', 'YR_YOUG', 'RIM_T', 'SANAQ', '27/11/2017', 'Y88074Q', 2, 100190813, 1, 33, 0, 33,
                 33, 67, 16.239, None],
                ['INES-YVESROCHER', 'YR_YOUG', 'RIM_T', 'RIMQ', '27/11/2017', None, 1, 100191290, 1, 13, 0, 13, 13, 13,
                 6.397, None],
                ['INES-YVESROCHER', 'YR_YOUG', 'RIM_T', 'MARWAQ', '27/11/2017', 'Y88074Q', 25, 100195183, 1, 8, 100, 0,
                 0, 132, 3.937, 'CADEAU_PTS']]
        wizard = self._import(rows)
        self.assertEqual(wizard.file_type, 'sales_detail')
        lines = self.env['yr.legacy.sale.line'].search([('shop_code', '=', 'YR_YOUG'), ('date', '=', date(2017, 11, 27))])
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines.mapped('store_id'), self.store)
        self.assertEqual(lines.filtered(lambda l: l.ticket == '2').partner_id, partner)
        self.assertFalse(lines.filtered(lambda l: l.ticket == '1').partner_id)
        self.assertEqual(lines.filtered(lambda l: l.ticket == '25').reason, 'CADEAU_PTS')
        self.assertEqual(set(lines.mapped('seller_name')), {'SANAQ', 'RIMQ', 'MARWAQ'})

    # ── sales detail ─────────────────────────────────────────────────────
    def _detail(self, ticket, day, cashier, seller, card, ref, ean, name, qty, price, discount, total, reason=None):
        return ['YR_YOUG', ticket, day, cashier, seller, 168479 if card else 0, card, 'SOUISSI' if card else None,
                'WAEL' if card else None, ref, ean, 56748, name, 'MAQUILLAGE', 'CN3', qty, price, discount, total,
                reason, None]

    def test_sales_detail(self):
        product = self.env['product.product'].create({'name': 'Crayon khôl test', 'default_code': '900106131',
                                                      'barcode': '3660009567488', 'list_price': 23})
        cashier = self.env['hr.employee'].create({'name': 'Rim Caissière', 'yr_fastmag_name': 'RIM'})
        self._import([NEW_HEADER, self._new_row(9940133181, 'SOUISSI', 'WAEL', datetime(1990, 1, 2))])
        day = datetime.combine(date.today() - timedelta(days=3), datetime.min.time())
        rows = [DETAIL_HEADER,
                self._detail(9199659, day, 'RIM', 'JBELI TEST', None, 900106131, 3660009567488, 'CRAYON', 1, 23, 0, 23),
                self._detail(9199659, day, 'RIM', 'JBELI TEST', None, 'DTT', 75229, 'DROIT DE TIMBRE', 1, 0.1, 0, 0.1),
                self._detail(9199667, day, 'RIM', 'SLIMENI TEST', 9940133181, 'X1', 3660009567488, 'CRAYON', 2, 23, 0,
                             46),
                self._detail(9199667, day, 'RIM', 'SLIMENI TEST', 9940133181, 'INCONNU', None, 'CREME', 1, 18, 100, 0,
                             'CADEAU_PTS'),
                self._detail(9199667, day, 'RIM', 'SLIMENI TEST', 9940133181, 'DTT', 75229, 'DROIT DE TIMBRE', 1, 0.1,
                             0, 0.1)]
        wizard = self._import(rows)
        self.assertEqual(wizard.file_type, 'sales_detail')
        Line = self.env['yr.legacy.sale.line']
        lines = Line.search([('shop_code', '=', 'YR_YOUG'), ('ticket', 'in', ['9199659', '9199667'])])
        self.assertEqual(len(lines), 5)
        first = lines.filtered(lambda l: l.ticket == '9199659' and l.sequence == 1)
        self.assertEqual((first.product_id, first.store_id, first.cashier_id), (product, self.store, cashier))
        self.assertEqual((first.seller_name, first.seller_id.name), ('JBELI TEST', 'JBELI TEST'))  # seller created
        self.assertTrue(lines.filtered(lambda l: l.product_ref == 'DTT').mapped('is_stamp') == [True, True])
        self.assertEqual(lines.filtered(lambda l: l.product_ref == 'X1').product_id, product)       # by EAN
        gift = lines.filtered(lambda l: l.reason == 'CADEAU_PTS')
        self.assertEqual((gift.discount, gift.amount, gift.product_id.id), (100, 0, False))
        wael = self.env['res.partner'].search([('customer_code', '=', '9940133181')])
        self.assertEqual(lines.filtered(lambda l: l.ticket == '9199667').partner_id, wael)
        # purchase history of the customer: one visit, the total of the ticket
        purchase = self.env['yr.legacy.purchase'].search([('card', '=', '9940133181')])
        self.assertEqual((len(purchase), purchase.store_id), (1, self.store))
        self.assertAlmostEqual(purchase.amount, 46.1)
        self.assertEqual(wael.crm_last_order_date, day.date())
        # re-import: nothing duplicated, employees not created twice
        self._import(rows)
        self.assertEqual(Line.search_count([('shop_code', '=', 'YR_YOUG'), ('ticket', 'in', ['9199659', '9199667'])]), 5)
        self.assertEqual(self.env['hr.employee'].search_count([('name', '=', 'JBELI TEST')]), 1)
        self.assertEqual(self.env['yr.legacy.purchase'].search_count([('card', '=', '9940133181')]), 1)
        # a seller created later in Employés is attached with « Rattacher aux employés »
        self._import(rows, create_sellers=False)
        slimeni = lines.filtered(lambda l: l.seller_name == 'SLIMENI TEST')
        slimeni.seller_id.unlink()
        self.assertFalse(slimeni.seller_id)
        employee = self.env['hr.employee'].create({'name': 'Slimeni Maram', 'yr_fastmag_name': 'slimeni test'})
        Line._link_employees()
        self.assertEqual(slimeni.seller_id, employee)

    # ── seller chosen at the till ────────────────────────────────────────
    def test_pos_order_seller(self):
        seller = self.env['hr.employee'].create({'name': 'Vendeuse test'})
        config = self.env['pos.config'].create({'name': 'Caisse vendeur test'})
        self.assertEqual(config.yr_seller_mode, 'none')      # enabled on the existing tills at install
        config.yr_seller_mode = 'required'
        self.assertIn({'id': seller.id, 'name': 'Vendeuse test'}, config.yr_seller_data)
        other = self.env['hr.employee'].create({'name': 'Autre test'})
        config.yr_seller_employee_ids = other
        self.assertEqual(config.yr_seller_data, [{'id': other.id, 'name': 'Autre test'}])
        config.yr_seller_mode = 'none'
        self.assertEqual(config.yr_seller_data, [{'id': other.id, 'name': 'Autre test'}])
        Order = self.env['pos.order']
        vals = Order._yr_seller_vals({'yr_seller_ref': seller.id})
        self.assertEqual(vals['yr_seller_id'], seller.id)
        self.assertFalse(Order._yr_seller_vals({'yr_seller_ref': 0})['yr_seller_id'])
        self.assertFalse(Order._yr_seller_vals({'yr_seller_ref': 999999999})['yr_seller_id'])
        self.assertEqual(Order._yr_seller_vals({'yr_seller_id': seller.id})['yr_seller_ref'], seller.id)
