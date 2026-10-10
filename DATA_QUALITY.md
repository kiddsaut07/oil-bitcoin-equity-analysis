# Contrôle de qualité des données

Ce document décrit ce que le pipeline vérifie réellement et ce qu'il a **mesuré** lors
de la dernière exécution. Les chiffres proviennent de
`data/processed/quality_report.json`, produit par le code.

## Contrôles obligatoires et où ils sont implémentés

| # | Contrôle | Implémentation | Test associé |
|---|---|---|---|
| 1 | Schéma et colonnes | `preprocessing.validate_schema` | `TestSchema` |
| 2 | Parsing et tri des dates | `preprocessing.parse_dates`, `sort_by_date` | `TestDates` |
| 3 | Doublons comptés avant suppression | `find_duplicates` puis `drop_duplicate_dates` | `TestDuplicates` |
| 4 | NaN, infinis, prix non positifs | `to_numeric_close`, `audit_quality` | `TestSchema`, `TestQualityAudit` |
| 5 | Couverture et écarts | `observed_frequency_days`, `max_gap_days`, `frame_gap_days` | `TestQualityAudit` |
| 6 | Valeurs manquantes par série | `audit_quality` | `TestQualityAudit` |
| 7 | Variations extrêmes signalées, jamais supprimées | `audit_quality` (seuil 20 %) | `test_audit_counts_extreme_moves` |
| 8 | Unités documentées | `data_loader.SERIES` | `TestSeriesRegistry` |
| 9 | Pertes dues à l'alignement | `alignment_report` | `TestAlignment` |
| 10 | Métadonnées de collecte conservées | `data/raw/{asset}_metadata.json` | `TestFredParsing`, `TestCoinbaseParsing` |

## Mesures réelles (exécution du 2026-10-10)

| Série | lignes brutes | 1re / dernière date | manquants | doublons | prix non positifs | écart médian | écart max |
|---|---|---|---|---|---|---|---|
| `WTI` | 1 565 | 2020-01-02 / 2025-12-31 | 65 (4,15 %) | 0 | **1 (−36,98)** | 1 j | 3 j |
| `BTC_USD` | 2 185 | 2020-01-01 / 2025-12-31 | 0 | 0 | 0 | 1 j | 2 j |
| `SP500` | 1 565 | 2020-01-02 / 2025-12-31 | 57 (3,64 %) | 0 | 0 | 1 j | 3 j |

Points notables, à connaître avant d'interpréter les résultats :

1. **Prix spot négatif du WTI.** Le 2020-04-20, `DCOILWTICO` vaut **−36,98 USD/baril**.
   Ce n'est pas une erreur de chargement : c'est une observation réelle du fournisseur.
   Conséquences/application des règles :
   - le rendement simple vers et depuis ce prix est `NaN` (BR-005, prix non positif) ;
   - le rendement logarithmique correspondant est `NaN` (BR-006) ;
   - l'indice base 100 passe brièvement sous 0, ce qui rend le drawdown inférieur à −100 % ;
     c'est signalé explicitement dans le notebook.
2. **Valeurs vides FRED.** 65 dates pour le WTI et 57 pour le S&P 500 n'ont pas de
   cotation. Elles ne sont ni interpolées ni reconstituées (BR-008) ; elles retirent
   simplement des dates au panel commun.
3. **Bitcoin perd 689 observations** à l'alignement (week-ends et jours fériés où les
   marchés américains sont fermés) ; le S&P 500 en perd 12, le WTI 4.
4. **Aucune observation n'est exclue par le filtre de période** : les séries commence
   déjà le 2020-01-01 ou le 2020-01-02.
5. **Rendements non calculables :** WTI 1 494 sur 1 496 dates (prix négatif et écart de
   calendrier), BTC_USD et SP500 1 495 (première date sans prédécesseur).

## Rapport qualité produit

`data/processed/quality_report.json` contient, par série : fournisseur, identifiant,
unité, devise, horodatage de collecte, nombre de lignes, bornes, doublons (et
exemples), manquants (nombre et pourcentage), prix non finis, prix non positifs,
écarts médian et maximal, variations supérieures à 20 %, minimum, maximum et dernière
valeur, observations exclues par la période, valeurs manquantes retirées de la fenêtre.

## Principe appliqué

Aucun contrôle ne masque une anomalie. Aucune valeur n'est interpolée, aucun outlier
n'est supprimé, aucun échecs de téléchargement n'est remplacé par des données
fictives (BR-008, BR-015, BR-020).