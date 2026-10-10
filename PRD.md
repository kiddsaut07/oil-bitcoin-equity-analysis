# PRD — Product Requirements Document

## 1. Résumé

Construire un notebook Python reproductible qui compare les prix et les rendements de trois actifs/séries : pétrole WTI, Bitcoin (BTC/USD) et indice de prix S&P 500.

## 2. Problème et motivation

Les trois séries représentent des marchés et des mécanismes différents. Une analyse commune permet de décrire leurs trajectoires, leur risque observé et leurs co-mouvements, sans supposer à l'avance une relation de causalité.

## 3. Utilisateur cible

Étudiant de L3 souhaitant apprendre Python, analyse de données, statistiques et notions de finance quantitative. Le notebook doit être pédagogique et défendable à l'oral.

## 4. Objectifs

- Utiliser des données historiques traçables.
- Documenter les fournisseurs, unités, fréquences et limites.
- Comparer l'évolution relative en base 100.
- Calculer et expliquer rendements, volatilité, drawdown et corrélations.
- Détecter les problèmes de qualité des données.
- Reproduire les résultats dans un environnement documenté.

## 5. Hors périmètre

- Conseil financier ou recommandations d'achat/vente.
- Prévision de prix ou stratégie de trading.
- Application web, tableau de bord interactif, API publique ou base de données.
- Données temps réel.
- Conclusions causales ou attribution d'événements économiques sans étude dédiée.

## 6. Fonctionnalités requises

### F-01 — Acquisition
Charger les séries depuis les fournisseurs documentés. En cas d'échec, afficher une erreur utile et ne pas remplacer les observations par des valeurs inventées.

### F-02 — Traçabilité
Enregistrer le fournisseur, l'identifiant de série, la date de récupération, les paramètres de requête, l'unité et la période disponible. Respecter les conditions de stockage et de redistribution.

### F-03 — Audit
Présenter dimensions, premières/dernières dates, doublons, fréquence observée, valeurs manquantes, valeurs non finies et statistiques descriptives.

### F-04 — Prétraitement
Convertir les dates, trier, dédupliquer selon une règle documentée, sélectionner la période et construire une période commune sans remplissage silencieux.

### F-05 — Visualisation des prix
Tracer chaque série séparément avec unité et source, puis comparer les évolutions normalisées en base 100.

### F-06 — Analyse des rendements
Calculer les rendements simples et, en option, logarithmiques. Afficher statistiques descriptives et distributions.

### F-07 — Risque
Calculer la volatilité quotidienne et annualisée (convention documentée) ainsi que le drawdown maximal.

### F-08 — Corrélations
Calculer la corrélation de Pearson sur les rendements explicitement alignés. Indiquer le nombre d'observations utilisé.

### F-09 — Conclusions
Produire des observations chiffrées, prudentes, reliées aux résultats, et une section sur les limites.

### F-10 — Reproductibilité
Documenter versions, paramètres, commandes et période réellement analysée. Le notebook doit pouvoir être exécuté de haut en bas.

## 7. Exigences non fonctionnelles

- Code lisible, fonctions de traitement testables.
- Aucun secret dans Git.
- Aucune dépendance payante obligatoire.
- Messages d'erreur clairs et contrôles explicites.
- Graphiques lisibles avec titre, axes, unités, légendes et sources.
- Tests unitaires ne dépendant pas d'un service externe en direct.

## 8. Livrables

- Notebook `notebooks/oil_bitcoin_equity_analysis.ipynb`.
- Modules réutilisables dans `src/`.
- Tests automatisés dans `tests/`.
- Documentation du dépôt.
- Figures exportées, si leur génération est activée.
- Rapport indiquant les sources et la période effectivement exploitées.

## 9. Hypothèses à valider avant implémentation

1. Série exacte et contrat de données du WTI.
2. Fournisseur BTC/USD et définition de la clôture quotidienne.
3. Disponibilité et profondeur historique du S&P 500 via la source retenue.
4. Fuseaux horaires, calendrier et règle d'alignement.
5. Conditions de réutilisation et de publication des données.
6. Environnement Python testé.

## 10. Questions de validation

Le projet répond-il à la question centrale avec des données comparables ? Les calculs sont-ils vérifiables ? Un tiers peut-il reproduire l'analyse ? Les limites sont-elles visibles et honnêtement expliquées ?
