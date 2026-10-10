# Images de documentation

Images utilisées par le `README.md`. Elles sont produites à partir des sorties du
pipeline (`data/processed/*.csv`), jamais recopiées à la main.

| Fichier | Contenu |
|---|---|
| `logo.svg` | logo du projet |
| `banner.svg` | bannière d'en-tête |
| `hero_base100.png` | indices base 100 des trois séries alignées (vue d'ensemble + zoom WTI/S&P 500) |
| `risk_volatilite_drawdown.png` | volatilité annualisée et drawdown |
| `matrice_correlation.png` | corrélation de Pearson des rendements alignés |

Régénération : charger `data/processed/prices_aligned.csv` et
`data/processed/returns_simple.csv` (produits par `python -m src.pipeline`) puis
tracer les mêmes courbes. Le notebook produit des équivalents dans
`outputs/figures/` (dossier non versionné).

Ces graphiques sont des visuels dérivés de données de marché publiques ; les
conditions de redistribution de FRED et de Coinbase n'ont pas pu être vérifiées
(voir `DATA_SOURCES.md`).
