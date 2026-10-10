# Conception technique

## Architecture proposée

- `notebooks/oil_bitcoin_equity_analysis.ipynb` : narration, exploration, tableaux et graphiques.
- `src/data_loader.py` : récupération et normalisation du format des sources.
- `src/preprocessing.py` : validation, dates, doublons et alignement.
- `src/metrics.py` : indices base 100, rendements, volatilité, drawdown, corrélation.
- `src/visualization.py` : fonctions de graphiques réutilisables.
- `src/pipeline.py` : orchestration des étapes 1 à 10 et interface en ligne de commande
  (`python -m src.pipeline`). Ajout justifié : le notebook et la ligne de commande
  appellent un point d'entrée unique, ce qui rend la séquence
  « téléchargement → qualité → alignement → calculs » reproductible sans dupliquer
  d'ordonnancement dans le notebook. Ce module ne contient aucun calcul nouveau.
- `tests/` : tests unitaires sur les fonctions déterministes.
- `data/raw/` : données originales, uniquement si leur stockage est permis.
- `data/processed/` : données nettoyées et alignées + `quality_report.json`,
  selon les règles de licence.
- `outputs/figures/` : figures exportées.
- `docs/` : spécifications et registre de décisions.

## Flux

1. Charger la configuration et les dates.
2. Télécharger les séries depuis les fournisseurs validés.
3. Enregistrer les métadonnées de collecte.
4. Valider les schémas et réaliser l'audit qualité.
5. Nettoyer les types et gérer les doublons selon une règle explicite.
6. Appliquer la période cible et la méthode d'alignement approuvée.
7. Calculer les indices normalisés et rendements.
8. Calculer les métriques et graphiques.
9. Générer une interprétation descriptive.
10. Exporter les figures et exécuter les tests.

## Principes de conception

- Séparer acquisition, transformation, calcul et présentation.
- Préférer des fonctions petites et testables.
- Garder les fonctions de calcul indépendantes du réseau.
- Injecter ou passer les données aux fonctions plutôt que télécharger à l'intérieur des calculs.
- Les erreurs réseau doivent être explicites.
- Ne jamais inclure de clé dans le notebook ou les logs.
- Documenter les versions et les paramètres.

## Couche réseau

Le transport HTTP est explicite et injecté (`src/data_loader.py`) afin que les tests
puissent simuler des pannes sans accès réseau, et que le comportement en cas d'échec
soit lisible. Détail et justification : `ADR/ADR-003-http-transport.md`.

## Gestion des dépendances

Utiliser `requirements.txt` pour une installation simple et `pyproject.toml` pour les métadonnées et la configuration Ruff/pytest. Maintenir les deux cohérents. Une version exacte des dépendances testées peut être ajoutée après validation sur la machine cible.

## Pas de base de données

Le projet ne justifie pas de base SQL pour la première version. CSV ou Parquet peuvent suffire, sous réserve des licences, de la taille et de la nécessité de conserver les données.
