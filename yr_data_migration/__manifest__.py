# -*- coding: utf-8 -*-
{
    'name': 'YR – Reprise fastmag (articles, clients, CA)',
    'version': '18.0.1.7.0',
    'category': 'Sales',
    'summary': 'Champs fastmag manquants (articles, clients, vendeur en caisse) et import des fichiers fastmag',
    'description': """
Reprise des données fastmag (Yves Rocher) dans Posify 18
========================================================

* Article : site, catégorie fastmag, marque, ligne, nature, conditionnement, genre, statut, date de création,
  fournisseur. Les axes / sous-axes deviennent des catégories du point de vente (axe › sous-axe).
* Client : sexe, code et ancien code fastmag, date d'entrée, premier achat, montant TTC figé à la migration,
  CA / visites / dernier achat / dernier magasin des 2 dernières années, segment et vendeuse fastmag, NPAI.
  Le numéro de carte devient le numéro client (et le code-barres scanné en caisse).
* Commande PdV : vendeur (employé, différent du caissier), choisi en caisse avant le paiement (réglable par caisse :
  non demandé, facultatif, obligatoire ; liste des vendeurs). Imprimé sur le ticket.
* Import dans Posify : un seul écran, le type de fichier est reconnu tout seul (magasins, articles, clients
  2017-2026, clients ancien système, liste client (codes Y…), CA clients, détail des ventes avec caissier et
  vendeur). Réimportable sans doublon. Un client sans vrai numéro de carte n'est pas importé ; les ventes sans
  carte retrouvent leur client par le code Y. Rapport détaillé (Excel) après chaque import.
* Ventes fastmag par vendeur : tableau croisé / liste des lignes de ventes importées.

S'appuie sur Fidélité & CRM (loyalty_tier_marketing) pour la fiche client (naissance, n° client, magasin).
""",
    'author': 'SATEM',
    'license': 'LGPL-3',
    'depends': ['loyalty_tier_marketing', 'point_of_sale', 'purchase', 'hr'],
    'external_dependencies': {'python': ['openpyxl']},
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'views/product_template_views.xml',
        'views/res_partner_views.xml',
        'views/pos_order_views.xml',
        'views/loyalty_store_views.xml',
        'views/hr_employee_views.xml',
        'views/pos_config_views.xml',
        'views/legacy_sale_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/migration_import_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'yr_data_migration/static/src/backend/**/*',
        ],
        'point_of_sale._assets_pos': [
            'yr_data_migration/static/src/pos/**/*',
        ],
    },
    'post_init_hook': '_post_init_hook',
    'installable': True,
    'application': False,
}
