# Dictionnaire des données

Fournisseurs et identifiants confirmés le 2026-10-10 (voir `DATA_SOURCES.md`) :
`WTI` ← FRED `DCOILWTICO`, `BTC_USD` ← Coinbase `BTC-USD`, `SP500` ← FRED `SP500`.

| Champ | Type attendu | Description | Contrôle |
|---|---|---|---|
| `date` | datetime/date | Date ou horodatage associé à l'observation | Parse valide, tri croissant, doublons signalés |
| `asset` | string | Identifiant interne : `WTI`, `BTC_USD`, `SP500` | Valeur autorisée |
| `close` | float | Valeur de prix/clôture fournie par la source | Valeur finie ; unité documentée |
| `unit` | string | Unité du prix, par ex. USD/baril, USD/BTC ou points d'indice | Non vide |
| `currency` | string | Devise de la série, si applicable | Documentée |
| `provider` | string | Nom du fournisseur | Non vide |
| `series_id` | string | Symbole ou identifiant source | Non vide |
| `retrieved_at` | datetime ISO 8601 | Date/heure de récupération | Inclure fuseau horaire |
| `source_url` | string | URL de la série ou de l'API | URL valide et documentée |

## Séries candidates

| Série interne | Série candidate | Unité attendue | Point à vérifier |
|---|---|---|---|
| `WTI` | FRED `DCOILWTICO` | USD par baril | Confirmé : **prix spot** (pas un contrat). 65 jours sans observation ; un prix négatif le 2020-04-20 ; conditions de réutilisation non vérifiées |
| `BTC_USD` | Coinbase Exchange `BTC-USD` | USD par BTC | Confirmé : plateforme unique, clôture journalière UTC, 300 bougies max par requête, découpage en fenêtres de 290 jours ; conditions de réutilisation non vérifiées |
| `SP500` | FRED `SP500` | points d'indice | Confirmé : indice de **prix** (dividendes exclus), 57 jours sans observation ; conditions de réutilisation non vérifiées |

## Artefacts produits

| Fichier | Contenu | Clé |
|---|---|---|
| `data/raw/{asset}.csv` | réponse fournisseur brute, colonnes `date`, `close` | non versionné |
| `data/raw/{asset}_metadata.json` | fournisseur, identifiant, endpoint, paramètres, horodatage, bornes | non versionné |
| `data/processed/prices_aligned.csv` | panel large aligné sur les dates communes | `date` |
| `data/processed/indices_base100.csv` | indices base 100 | `date` |
| `data/processed/returns_simple.csv` | rendements simples (`NaN` si prix non positif ou écart > 7 j) | `date` |
| `data/processed/returns_log.csv` | rendements logarithmiques (`NaN` si prix non positif) | `date` |
| `data/processed/drawdowns.csv` | drawdown de chaque indice base 100 | `date` |
| `data/processed/quality_report.json` | audit qualité, alignement, paramètres d'annualisation | — |

## Tables dérivées

- `normalized_prices` : séries alignées et converties en base 100.
- `returns` : rendements simples, éventuellement logarithmiques, selon les règles documentées.
- `metrics_summary` : statistiques descriptives par série.
- `correlation_matrix` : corrélation de Pearson sur rendements alignés.
- `drawdown_series` : drawdown de chaque série selon la convention retenue.

Les noms exacts peuvent évoluer, mais leur signification doit rester documentée.
