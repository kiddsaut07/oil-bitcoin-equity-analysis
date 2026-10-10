# Registre des sources de données

## Principe

Ce registre ne décrit que des sources **réellement testées depuis
l'environnement du projet**, avec la date, la commande et le résultat du test.
Une source non vérifiable est signalée comme telle : elle n'est pas utilisée.

## Source 1 — Pétrole WTI

- **Fournisseur retenu :** FRED — Federal Reserve Bank of St. Louis (données publiées par
  l'U.S. Energy Information Administration).
- **Identifiant de série :** `DCOILWTICO`.
- **Page de la série :** https://fred.stlouisfed.org/series/DCOILWTICO
- **Endpoint utilisé :** https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILWTICO&cosd=2020-01-01&coed=2025-12-31
- **Authentification :** aucune clé requise pour cet export CSV.
- **Fréquence :** journalière, jours ouvrés américains.
- **Unité :** USD par baril.
- **Définition :** prix spot quotidien du WTI à Cushing (Oklahoma). Ce n'est **pas**
  un contrat à terme ; le contrat `CL` n'a pas été retenu.
- **Convention de clôture :** cours spot quotidien ; l'heure exacte n'est pas publiée
  par la source (à documenter comme limite).
- **Limites de requête :** l'export accepte `cosd` / `coed` pour borner la période ;
  une période 2020-2025 tient en une requête de quelques dizaines de kilo-octets.
- **Vérification effectuée (2026-10-10, depuis cet environnement) :** HTTP 200,
  1 565 lignes, premières observations `2020-01-02`, dernière `2025-12-31`,
  **65 valeurs vides** (jours sans cotation, mainly des jours fériés).
- **Conditions d'utilisation : NON VÉRIFIÉES.** La page https://fred.stlouisfed.org/legal/
  était injoignable depuis cet environnement (timeouts répétés). À lire avant toute
  rediffusion. Les données ne sont pas versionnées dans Git.

## Source 2 — Bitcoin BTC/USD

- **Fournisseur retenu :** Coinbase Exchange — API publique de données de marché.
- **Identifiant de produit :** `BTC-USD`.
- **Documentation utilisée :** https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles
- **Endpoint :** `https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=86400&start=...&end=...`
- **Authentification :** aucune clé requise pour cet endpoint public.
- **Fréquence :** journalière, 7 jours sur 7.
- **Unité :** USD par BTC.
- **Schéma de réponse vérifié :** `[time, low, high, open, close, volume]`, `time` en
  secondes UTC ; l'analyse utilise le champ `close`.
- **Convention de clôture :** bougie daily UTC (`granularity=86400`), clôture = dernier
  échange de la journée UTC. Cette clôture n'est pas alignée sur la séance américaine.
- **Limites de requête vérifiées :** maximum **300 bougies par requête** — une requête
  sur 2020-2025 est rejetée avec `Count of aggregations requested exceeds 300`
  (erreur HTTP 400 observée). Le pipeline découpe donc la période en fenêtres de
  290 jours (8 requêtes sur la période cible) avec une courte pause entre les appels.
  La documentation indique aussi que des bougies peuvent précéder le `start` demandé :
  le filtre final impose la fenêtre exacte.
- **Conditions d'utilisation : NON VÉRIFIÉES.** Les CGU Coinbase n'ont pas été lues
  depuis cet environnement ; à vérifier sur https://www.coinbase.com/legal/user-agreement/
  avant toute rediffusion. Les données ne sont pas versionnées dans Git.

### Alternative évaluée

Kraken (`https://api.kraken.com/0/public/OHLC`, paire `XXBTZUSD`) répond également
sans clé et autorise 720 bougies par requête. Elle n'a pas été retenue : le schéma
renvoie des champs nommés, la dernière bougie est souvent incomplète et la
documentation de clôture est moins explicite. Ce choix est tracé dans
`ADR/ADR-001-data-sources.md`.

## Source 3 — S&P 500

- **Fournisseur retenu :** FRED (données publiées par S&P Dow Jones Indices, LLC).
- **Identifiant de série :** `SP500`.
- **Page de la série :** https://fred.stlouisfed.org/series/SP500
- **Endpoint utilisé :** https://fred.stlouisfed.org/graph/fredgraph.csv?id=SP500&cosd=2020-01-01&coed=2025-12-31
- **Authentification :** aucune clé requise pour cet export CSV.
- **Fréquence :** journalière, jours ouvrés américains.
- **Unité :** points d'indice.
- **Limite importante (BR-018) :** série d'**indice de prix** ; les **dividendes ne sont
  pas inclus**. La comparaison avec un indice de rendement total serait faussée.
- **Vérification effectuée (2026-10-10) :** HTTP 200, 1 565 lignes,
  `2020-01-02` → `2025-12-31`, **57 valeurs vides**.
- **Conditions d'utilisation : NON VÉRIFIÉES** (voir Source 1).

## Note sur l'API officielle FRED

L'API officielle `https://api.stlouisfed.org/fred/series/observations` exige une clé
gratuite (`FRED_API_KEY`). Elle n'a pas été utilisée ici : l'export CSV public permet
une reproduction sans compte. Si un tiers souhaite l'API officielle, il suffit de
remplacer `fetch_fred_series` dans `src/data_loader.py` ; le reste du pipeline est
inchangé.

## Note sur l'EIA

L'EIA expose une API v2 officielle (`https://api.eia.gov/v2/`) qui nécessite également
une clé gratuite. L'appel avec la clé de démonstration `DEMO_KEY` n'a pas répondu
depuis cet environnement : la source EIA directe n'est donc **pas** implémentée.
`DCOILWTICO` (publiée par l'EIA, distribuée par FRED) couvre le besoin.

## Biblio

| Besoin | Fournisseur | Statut |
|---|---|---|
| WTI spot USD/baril | FRED `DCOILWTICO` | vérifié, en usage |
| BTC/USD | Coinbase `BTC-USD` | vérifié, en usage |
| S&P 500 | FRED `SP500` | vérifié, en usage |
| WTI via EIA direct | EIA API v2 | non implémenté (clé requise) |
| BTC/USD via agrégat | Kraken OHLC | évaluée, non retenue |

## Journal de collecte

Le pipeline enregistre automatiquement, pour chaque série, dans
`data/raw/{asset}_metadata.json` :

1. fournisseur et identifiant ;
2. URL de page et endpoint de requête (sans secret) ;
3. horodatage de collecte ISO 8601 avec fuseau ;
4. paramètres de requête ;
5. nombre de lignes reçues, première et dernière observation ;
6. unité, devise, fréquence et convention de clôture ;
7. rappel des conditions d'utilisation.

Le rapport de contrôle qualité est écrit dans `data/processed/quality_report.json`.
Aucune clé API n'est stockée dans le dépôt, le notebook ou ces fichiers.