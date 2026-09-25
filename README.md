# Reprise fastmag → Odoo 18 (Yves Rocher) — `yr_data_migration`

Dossier d'addons : copier `yr_data_migration/` dans `/home/Administrateur/addons` (le nom du dossier doit rester
`yr_data_migration`, sans espace), puis :

```bash
sudo systemctl stop odoo
sudo -u odoo odoo -c /etc/odoo/odoo.conf -d POSIFY-TEST -i yr_data_migration --stop-after-init
sudo systemctl start odoo
```

Dépend de **Fidélité & CRM** (`loyalty_tier_marketing`), `point_of_sale`, `purchase`. Remplace l'ancien dossier
« added fields » (à supprimer du serveur : son nom avec un espace empêchait la mise à jour de la liste des apps).

## Import (dans Odoo, pas de script)

**Fidélité & CRM › Configuration › Reprise fastmag** (ou Inventaire › Configuration). Choisir un fichier : son type
est **reconnu tout seul** d'après les en-têtes.

| Fichier fastmag | Ce qui est créé / mis à jour |
|---|---|
| Fiche article (`réf article`, `EAN bar`…) | Articles stockables, vendus en caisse : référence, code-barres, désignation, prix, unité. **Axe › sous-axe = catégories du point de vente** (MAQUILLAGE › TEINT), utilisées par l'inventaire et le CRM. Fournisseur (fiche fournisseur + tarif fournisseur). Site, catégorie fastmag, marque, ligne, nature, conditionnement, genre, statut, date de création dans l'onglet « Fiche fastmag ». « bu » n'est pas repris. |
| Clients 2017-2026 (`CardNumbre`…) | Fiche client : **le n° de carte devient le n° client et le code-barres** (l'ancienne carte fonctionne en caisse), nom, adresse, téléphone / mobile, e-mail, naissance jour / mois (+ année si connue), date d'entrée, premier achat, magasin (`CodeShop`), vendeuse, montant TTC figé à la migration. |
| Clients ancien système (`numCliente`…) | Idem, + sexe, NPAI, segment fastmag. L'année 2000 des dates de naissance = année inconnue (option). Téléphones `22.51.36.90` → `22513690`, rangés en mobile s'ils commencent par 2, 4, 5 ou 9. |
| CA clients 2 ans (`Cartefidelite`, `TOTALCA`…) | **Historique d'achats** (une ligne par carte, jour et magasin). Il compte dans Fidélité & CRM : statut client, premier / dernier achat, CA, dernier magasin, segments, tableau de bord. |

* Ordre libre : l'historique d'une carte encore inconnue est gardé et rattaché quand le client est importé.
* Réimportable : rien n'est créé en double (article = référence ou code-barres ; client = n° de carte ; achat = carte
  + jour + magasin). Les champs vides des clients existants sont complétés ; rien n'est effacé ; le montant de migration
  reste figé.
* Lignes vides, dates en texte (`16/09/2019`), `20/11/0000` (jour et mois seulement), `00/01/0000` (ignoré), codes
  numériques lus comme du texte.
* Magasins : renseigner le **Code magasin fastmag** (ex. `YR_YOUG`) sur chaque magasin (Fidélité & CRM ›
  Configuration › Magasins) ; l'import liste les codes inconnus. Réimporter ensuite le fichier.
* Résultat affiché : créés, mis à jour, lignes en erreur avec la raison.

## Autres ajouts

* Commande du point de vente : **Vendeur** (différent du caissier) + code vendeur fastmag.
* Groupe « YR : voir les données de migration figées » (montant TTC et date de migration).

## Tests

`odoo-bin -d <db> -i yr_data_migration --test-tags /yr_data_migration` — fichiers construits comme les exports
fastmag (données fictives) : articles (axes, fournisseurs, doublons de code-barres, réimport, archivage), clients
des deux fichiers (dates de naissance, téléphones, magasins, montant figé, réimport), historique d'achats et
statut client, fichier non reconnu.
