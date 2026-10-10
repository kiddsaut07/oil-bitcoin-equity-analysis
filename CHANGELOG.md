# Changelog

Les changements notables sont consignés ici.

## Unreleased
- Implémentation complète : `src/data_loader.py`, `src/preprocessing.py`,
  `src/metrics.py`, `src/visualization.py` et `src/pipeline.py`.
- Sources validées : FRED `DCOILWTICO` (WTI spot), Coinbase `BTC-USD`,
  FRED `SP500` ; documentées dans `DATA_SOURCES.md`.
- ADR-001 (sources), ADR-002 (alignement) et ADR-003 (transport HTTP) rédigés.
- Pipeline de données : téléchargement, métadonnées de collecte, audit qualité,
  déduplication, filtrage de période, alignement, exports CSV et rapport JSON.
- Métriques : base 100, rendements simples et logarithmiques, volatilité annuelle
  (convention 252 documentée), volatilité glissante, drawdown, corrélation de Pearson.
- Figures réutilisables avec titre, axes, unités, légende, période et source.
- Notebook `notebooks/oil_bitcoin_equity_analysis.ipynb` en 16 sections, exécuté
  de bout en bout sans erreur.
- 86 tests unitaires sans réseau, exécutés et passants.
- Qualité statique validée avec Ruff 0.17.0 (`check` et `format --check`).
- Cas réel documenté : prix spot WTI négatif le 2020-04-20, traitement explicite
  selon BR-005, BR-006 et BR-014.

## Antérieur
- Dossier initial de cadrage, méthodologie, architecture et qualité.
- Sources et paramètres de données marqués comme candidats à vérifier.
