# Reprise fastmag → Posify 18 (Yves Rocher) — `yr_data_migration`

Dossier d'addons : copier `yr_data_migration/` dans `/home/Administrateur/addons` (le nom du dossier doit rester
`yr_data_migration`, sans espace), puis :

```bash
sudo systemctl stop odoo
sudo -u odoo odoo -c /etc/odoo/odoo.conf -d POSIFY-TEST -i yr_data_migration --stop-after-init
sudo systemctl start odoo
```

Dépend de **Fidélité & CRM** (`loyalty_tier_marketing`), `point_of_sale`, `purchase`, `hr` (Employés). Remplace l'ancien dossier
« added fields » (à supprimer du serveur : son nom avec un espace empêchait la mise à jour de la liste des apps).

## Import (dans Posify, pas de script)

**Fidélité & CRM › Configuration › Reprise fastmag** (ou Inventaire › Configuration). Choisir un fichier : son type
est **reconnu tout seul** d'après les en-têtes.

| Fichier fastmag | Ce qui est créé / mis à jour |
|---|---|
| Liste des magasins (`magasin`, `code`, ou 2 colonnes sans en-tête : `AZUR` \| `23`) | Magasins de Fidélité & CRM : créés s'ils manquent, sinon le code est mis à jour (l'ancien code reste reconnu). `eshop` devient le site web. |
| Fiche article (`réf article`, `EAN bar`…) | Articles stockables, vendus en caisse : référence, code-barres, désignation, prix, unité. **Axe › sous-axe = catégories du point de vente** (MAQUILLAGE › TEINT), utilisées par l'inventaire et le CRM. Fournisseur (fiche fournisseur + tarif fournisseur). Site, catégorie fastmag, marque, ligne, nature, conditionnement, genre, statut, date de création dans l'onglet « Fiche fastmag ». « bu » n'est pas repris. |
| Clients 2017-2026 (`CardNumbre`…) | Fiche client : **le n° de carte devient le n° client et le code-barres** (l'ancienne carte fonctionne en caisse), nom, adresse, téléphone / mobile, e-mail, naissance jour / mois (+ année si connue), date d'entrée, premier achat, magasin (`CodeShop`), vendeuse, montant TTC figé à la migration. |
| Clients ancien système (`numCliente`…) | Idem, + sexe, NPAI, segment fastmag. L'année 2000 des dates de naissance = année inconnue (option). Téléphones `22.51.36.90` → `22513690`, rangés en mobile s'ils commencent par 2, 4, 5 ou 9. |
| CA clients 2 ans (`Cartefidelite`, `TOTALCA`…) | **Historique d'achats** (une ligne par carte, jour et magasin). Il compte dans Fidélité & CRM : statut client, premier / dernier achat, CA, dernier magasin, segments, tableau de bord. |
| Détail des ventes (`CodeMag`, `Vente`, `Utilisateur`, `Vendeur`…) | **Ventes fastmag par vendeur** (Fidélité & CRM › Analyse, Point de vente › Analyse) : une ligne par ligne de ticket avec magasin, ticket, **utilisateur = caissier**, **vendeur**, client, article (réf. puis EAN), quantité, prix, remise, total, motif. `DTT` = droit de timbre (pas un article). Les vendeurs deviennent des Employés (option), proposés en caisse. Les totaux par carte / jour / magasin alimentent l'historique d'achats (même clé que le fichier CA : pas de doublon). |

* Ordre libre : l'historique d'une carte encore inconnue est gardé et rattaché quand le client est importé.
* Réimportable : rien n'est créé en double (article = référence ou code-barres ; client = n° de carte ; achat = carte
  + jour + magasin). Les champs vides des clients existants sont complétés ; rien n'est effacé ; le montant de migration
  reste figé.
* Lignes vides, dates en texte (`16/09/2019`), `20/11/0000` (jour et mois seulement), `00/01/0000` (ignoré), codes
  numériques lus comme du texte.
* Magasins : importer d'abord la liste des magasins. `YR_AZUR` est reconnu d'après le nom (AZUR ; `YR_YOUG` →
  YOUGOSLAVIE) et retenu dans le **Code magasin fastmag**. Sinon, le renseigner sur le magasin (Fidélité & CRM ›
  Configuration › Magasins) ; l'import liste les codes inconnus. Réimporter ensuite le fichier.
* Employés : le champ **Nom(s) fastmag** (ex. `RIM`, `JBELI RYM`) rattache les caissiers / vendeurs dont le nom
  diffère ; bouton « Rattacher aux employés » dans la liste des ventes fastmag.
* Résultat affiché : créés, mis à jour, lignes en erreur avec la raison.

## Autres ajouts

* **Vendeur en caisse** : au clic sur « Paiement », la liste des vendeurs s'ouvre (« Qui a servi le client ? »). Le
  caissier reste la personne connectée. Réglage par caisse (Point de vente › Configuration › Paramètres ›
  « Vendeur avant paiement ») : non demandé / facultatif / obligatoire, et liste des vendeurs (vide = tous les
  employés). Les caisses existantes passent en « obligatoire » à l'installation / mise à jour. Modifiable avant le
  paiement (Actions › Vendeur), imprimé sur le ticket, visible et regroupable dans les commandes (champ Vendeur).
* Groupe « YR : voir les données de migration figées » (montant TTC et date de migration).

## Tests

`odoo-bin -d <db> -i yr_data_migration --test-tags /yr_data_migration` — fichiers construits comme les exports
fastmag (données fictives) : articles (axes, fournisseurs, doublons de code-barres, réimport, archivage), clients
des deux fichiers (dates de naissance, téléphones, magasins, montant figé, réimport), historique d'achats et
statut client, liste des magasins (avec / sans en-tête), détail des ventes (caissier, vendeur, articles,
timbre, historique client, réimport, rattachement des employés), vendeur des commandes de caisse, fichier non reconnu.
