# ADR-001 — Choix des sources de données

- **Statut :** accepté (vérifications effectuées le 2026-10-10 depuis l'environnement du projet).
- **Contexte :** le projet compare WTI, BTC/USD et S&P 500 sur 2020-01-01 → 2025-12-31.
  Les sources candidates étaient EIA (WTI), FRED `SP500` et un fournisseur BTC/USD non arrêté.
- **Décision :**

  | Série | Fournisseur | Identifiant | Accès |
  |---|---|---|---|
  | WTI spot | FRED (données EIA) | `DCOILWTICO` | export CSV public, sans clé |
  | BTC/USD | Coinbase Exchange | `BTC-USD` | endpoint public `candles`, sans clé |
  | S&P 500 | FRED | `SP500` | export CSV public, sans clé |

- **Motifs :** traçabilité complète (page de série + endpoint + métadonnées de collecte),
  absence de dépendance payante, absence de clé secrète, disponibilité effective sur
  toute la période, documentation de la convention de clôture.
- **Vérifications effectuées :** HTTP 200 sur les trois endpoints ; `DCOILWTICO` et `SP500`
  couvrent `2020-01-02` → `2025-12-31` (1 565 lignes, respectivement 65 et 57 valeurs
  vides) ; `BTC-USD` accepte `granularity=86400` et refuse plus de 300 bougies par requête
  (erreur 400 confirmée), d'où un découpage en fenêtres de 290 jours.
- **Alternatives évaluées :**
  - *EIA API v2* pour le WTI : exige une clé gratuite et l'appel avec `DEMO_KEY` n'a pas
    répondu depuis cet environnement → non implémentée.
  - *Kraken OHLC (`XXBTZUSD`)* : accessible sans clé, 720 bougies par requête, mais schéma
    différent et clôture moins bien documentée → non retenue.
  - *API FRED officielle* : exige `FRED_API_KEY` ; l'export CSV public suffit.
- **Conséquences :** le projet n'exige aucun compte ni clé. Les données brutes ne sont pas
  versionnées (`data/raw/` est ignoré par Git) car les conditions de redistribution de FRED
  et de Coinbase **n'ont pas pu être vérifiées** depuis cet environnement ; elles doivent
  être lues avant toute publication des données.
- **Point restant à valider par le propriétaire du projet :** lecture des pages
  https://fred.stlouisfed.org/legal/ et https://www.coinbase.com/legal/user-agreement/
  avant de décider si les données brutes peuvent être publiées.