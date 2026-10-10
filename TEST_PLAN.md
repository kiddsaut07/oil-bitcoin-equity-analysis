# Plan de tests

## Principes

Les tests des fonctions analytiques utilisent des données synthétiques déterministes
et **n'accèdent jamais à Internet** : un transport HTTP factice est injecté dans
`src/data_loader.py` (paramètre `transports`). Les données de test ne sont jamais
mélangées aux observations historiques (BR-020).

## Exécution réelle

Commande : `python -m pytest` (environnement `.venv`, Python 3.13.12).

Résultat de la dernière exécution : **86 passed** (aucun échec, aucun test ignoré).

## Couverture des tests unitaires

### Prétraitement (`tests/test_preprocessing.py`)
| Cas attendu | Test |
|---|---|
| colonne manquante → `SchemaError` | `test_missing_column_raises` |
| cadre vide → `EmptyDataError` | `test_empty_frame_raises` |
| marqueurs FRED (`.`, vide) → `NaN` | `test_missing_tokens_become_nan` |
| prix illisible → `NaN` | `test_unparsable_price_becomes_nan` |
| date invalide → `SchemaError` | `test_invalid_date_raises` |
| `NaT` accepté en mode `coerce` | `test_coerce_marks_invalid_dates_as_nat` |
| horodatage fuseau → date UTC normalisée | `test_aware_timestamps_are_normalised` |
| tri chronologique | `test_dates_are_parsed_and_sorted` |
| doublons détectés avant suppression | `test_duplicates_are_detected_before_removal` |
| déduplication : dernière occurrence conservée | `test_drop_duplicate_dates_keeps_last` |
| bornes de période incluses | `test_bounds_are_inclusive` |
| période hors données → vide | `test_period_outside_data_returns_empty` |
| manquants, doublons et écarts comptés | `test_audit_counts_missing_and_duplicates` |
| prix non positifs détectés | `test_audit_flags_non_positive_prices` |
| variations extrêmes signalées | `test_audit_counts_extreme_moves` |
| alignement sur dates communes | `test_alignment_keeps_only_common_dates` |
| pertes d'alignement rapportées | `test_alignment_report_documents_losses` |
| intersection vide → erreur explicite | `test_empty_intersection_raises` |
| alignement refusé si doublons | `test_alignment_refuses_duplicates` |
| agrégation hebdomadaire ISO | `test_last_observation_of_each_week_is_kept` |
| format long | `test_pivot_long_restores_asset_column` |
| prix non finis → erreur | `TestPositiveAssertion` |

### Métriques (`tests/test_metrics.py`)
| Cas attendu | Test |
|---|---|
| base 100 : `[10, 20, 15]` → `[100, 200, 150]` | `test_known_example` |
| base et sa date reportées | `test_normalised_panel_reports_bases` |
| base nulle/négative → erreur | `test_non_positive_base_raises` |
| rendement simple : `[100, 110]` → `0,10` | `test_known_example` |
| rendement négatif | `test_downward_move` |
| écart > seuil → `NaN` | `test_gap_beyond_threshold_is_excluded` |
| seuil désactivable | `test_gap_control_can_be_disabled` |
| rendement log : `ln(1,1)` | `test_known_example` |
| prix non positif → `NaN` + avertissement | `test_non_positive_price_yields_nan_and_warning` |
| prix non positif → erreur si `on_invalid="raise"` | `test_non_positive_price_can_raise` |
| annualisation `std × √N` | `test_annualisation_formula` |
| 252 ≠ 365 | `test_convention_365_differs_from_252` |
| moins de 2 observations → erreur | `test_single_observation_raises` |
| rendements constants → volatilité nulle | `test_constant_returns_have_zero_volatility` |
| fenêtre glissante sans valeur au démarrage | `test_rolling_values_start_after_window` |
| drawdown `100 → 80` = `-20 %` | `test_known_peak_and_trough` |
| drawdown toujours ≤ 0 | `test_drawdown_is_never_positive` |
| reconstruction de richesse | `test_wealth_reconstruction_matches_prices` |
| statistiques sur série connue | `test_descriptive_statistics_on_known_series` |
| série vide → erreur | `test_empty_series_raises` |
| séries identiques → corrélation 1 | `test_identical_series_correlate_perfectly` |
| séries opposées → corrélation −1 | `test_opposite_series_correlate_negatively` |
| observations appariées comptées | `test_pairwise_observations_count` |
| série constante → corrélation `NaN` signalée | `test_constant_series_is_flagged_and_gives_nan_correlation` |

### Récupération (`tests/test_data_loader.py`)
| Cas attendu | Test |
|---|---|
| registre des trois séries | `TestSeriesRegistry` |
| S&P 500 déclaré indice de prix | `test_sp500_is_declared_as_price_index` |
| série inconnue → erreur | `test_unknown_series_raises` |
| CSV FRED parsé | `test_csv_is_parsed_into_date_and_close` |
| marqueur manquant → `NaN` | `test_missing_marker_becomes_nan` |
| réponse vide / colonnes inattendues → erreur | `TestFredParsing` |
| URL et métadonnées conformes, sans clé | `test_fetch_builds_expected_url_and_metadata` |
| schéma Coinbase, champ `close` utilisé | `test_candles_use_the_close_field` |
| réponse d'erreur / vide / JSON invalide → erreur | `TestCoinbaseParsing` |
| période découpée en fenêtres de 290 jours | `test_long_period_is_split_into_chunks` |
| filtre de période strict | `test_period_filter_removes_out_of_window_candles` |
| HTTP 404 → erreur immédiate | `test_http_404_raises_data_source_error` |
| échec transitoire → reprise puis succès | `test_transient_failure_is_retried_then_succeeds` |
| échec réseau → **aucune donnée de secours** | `test_network_failure_never_returns_fabricated_data` |
| erreur transportée jusqu'à l'appelant | `test_fetch_series_propagates_error` |
| `HTTPError` urllib converti en `TransportError` | `test_urllib_transport_wraps_http_errors` |

### Pipeline (`tests/test_pipeline.py`)
| Cas attendu | Test |
|---|---|
| chaîne complète hors ligne | `test_pipeline_aligns_and_computes_every_step` |
| artefacts et rapport qualité écrits | `test_artifacts_are_written_with_metadata` |
| manquants documentés, panel réduit | `test_quality_report_documents_missing_values` |
| bornes incluses | `test_period_filter_is_inclusive` |
| copie locale absente → message actionnable | `test_missing_local_copy_raises_actionable_error` |
| période inversée → erreur | `test_inverted_period_raises` |
| entrées non triées et dupliquées nettoyées | `test_unsorted_duplicate_raw_input_is_cleaned` |
| série hebdomadaire exploitable | `TestWeeklySensitivity` |

## Tests d'intégration réseau (non exécutés automatiquement)

Non inclus dans la suite unitaire, car ils dépendent du réseau :

1. `python -m src.pipeline --assets SP500 --start 2024-01-01 --end 2024-02-01`
   pour vérifier l'accès réel à une source ;
2. comparaison des métadonnées de `data/raw/*_metadata.json` avec la page fournisseur ;
3. vérification que le nombre d'observations et les bornes restent cohérentes après
   révision éventuelle de la source.

Ces tests ont été exécutés manuellement lors du développement ; le résultat est
rapporté dans `DATA_SOURCES.md`.

## Règles de rédaction

- Une assertion doit être vérifiable à la main (`0,10`, `ln(1,1)`, `[100, 200, 150]`).
- Aucun test ne dépend d'un ordre d'exécution ou d'un état partagé.
- Aucun test n'est déclaré réussi sans exécution réelle.