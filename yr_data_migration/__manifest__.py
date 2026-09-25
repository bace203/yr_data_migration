# -*- coding: utf-8 -*-
{
    'name': 'YR – Reprise fastmag (articles, clients, CA)',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Champs fastmag manquants (articles, clients, vendeur PdV) et import des fichiers fastmag',
    'description': """
Reprise des données fastmag (Yves Rocher) dans Odoo 18
======================================================
* Article : site, catégorie fastmag, marque, ligne, nature, conditionnement, genre, statut, date de création,
  fournisseur. Les axes / sous-axes deviennent des catégories du point de vente (axe › sous-axe).
* Client : sexe, code et ancien code fastmag, date d'entrée, premier achat, montant TTC figé à la migration,
  CA / visites / dernier achat / dernier magasin des 2 dernières années, segment et vendeuse fastmag, NPAI.
  Le numéro de carte devient le numéro client (et le code-barres scanné en caisse).
* Commande PdV : vendeur (différent du caissier).
* Import dans Odoo : un seul écran, le type de fichier est reconnu tout seul (articles, clients 2017-2026,
  clients ancien système, CA clients). Réimportable sans doublon.
S'appuie sur Fidélité & CRM (loyalty_tier_marketing) pour la fiche client (naissance, n° client, magasin).
""",
    'author': 'SATEM',
    'license': 'LGPL-3',
    'depends': ['loyalty_tier_marketing', 'point_of_sale', 'purchase'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/product_template_views.xml',
        'views/res_partner_views.xml',
        'views/pos_order_views.xml',
        'views/loyalty_store_views.xml',
        'wizard/migration_import_views.xml',
    ],
    'installable': True,
    'application': False,
}
