# Méthodologie statistique

## 1. Périmètre temporel

Période cible : `2020-01-01` à `2025-12-31`, bornes incluses. Le rapport doit donner la période effectivement exploitable. Définir précisément si la « période commune » signifie intersection des dates observées ou fenêtre de dates commune avec calendrier explicite.

## 2. Prix et unités

Les niveaux bruts ne sont pas directement comparables : USD/baril, USD/BTC et points d'indice sont des unités différentes. Les prix bruts sont présentés séparément et leurs unités sont affichées.

## 3. Normalisation base 100

Pour chaque série :

`index_t = price_t / price_base * 100`

`price_base` correspond à la première observation valide choisie par la règle d'alignement approuvée. Afficher la date et la valeur de référence. Ne pas confondre une base 100 avec un rendement total incluant dividendes.

## 4. Rendements

Rendement simple :

`return_t = price_t / price_(t-1) - 1`

Rendement logarithmique, optionnel :

`log_return_t = ln(price_t / price_(t-1))`

Le rendement logarithmique exige des prix strictement positifs. Les intervalles entre observations doivent être contrôlés : des dates non consécutives peuvent représenter des horizons différents.

## 5. Alignement des calendriers

**Décision retenue (ADR-002, acceptée).** L'analyse principale utilise l'**intersection
des dates observées** des trois séries, sans forward-fill ni interpolation. Une agrégation
hebdomadaire (dernière observation de chaque semaine ISO) est calculée en **analyse de
sensibilité** dans le notebook. Effet mesuré : le panel commun compte 1 496 dates, contre
1 508 (S&P 500), 1 500 (WTI) et 2 185 (Bitcoin) avant alignement.

Bitcoin cote généralement en continu, tandis que les marchés actions et les marchés pétroliers ont des calendriers différents. Deux approches sont envisageables :

- **Quotidien sur dates communes :** simple, mais exclut les dates où une série n'a pas d'observation et peut sélectionner des jours particuliers.
- **Hebdomadaire :** peut faciliter la comparaison, à condition de définir la règle de clôture hebdomadaire, le fuseau et le traitement des semaines incomplètes.

Choisir une méthode principale et justifier le choix. Ne pas forward-fill par défaut. Les observations du même jour peuvent ne pas correspondre au même instant de clôture.

## 6. Statistiques descriptives

Pour chaque série de rendements, calculer au minimum : nombre d'observations, moyenne, médiane, écart-type, minimum, maximum et quantiles pertinents. Afficher les unités ou le format en pourcentage de manière cohérente.

## 7. Volatilité

Volatilité quotidienne : écart-type des rendements selon la convention de l'échantillon explicitée.

Volatilité annualisée, si utilisée :

`annualized_volatility = daily_std * sqrt(N)`

`N` doit être justifié. Une convention de 252 séances convient souvent à des séries de marchés traditionnels, mais n'est pas automatiquement adaptée à Bitcoin qui cote 365 jours par an. Une comparaison doit utiliser des conventions explicites et expliquer leurs effets.

**Convention appliquée ici.** Toutes les statistiques comparatives portent sur le panel
aligné, dont les trois séries partagent le même calendrier de séances : `N = 252` pour
les trois, sinon la comparaison serait faussée. Le notebook affiche en parallèle la
valeur `N = 365` à titre informatif pour montrer l'effet du choix (volatilité annualisée
multipliée par `√365 / √252 ≈ 1,20`). L'écart-type observé est toujours présenté séparément
de la volatilité annualisée.

## 8. Drawdown

À partir d'une série de valeur cumulée cohérente :

`drawdown_t = wealth_t / running_peak_t - 1`

Le drawdown maximal est le minimum de cette série. Documenter comment la série de richesse est construite et la date du creux.

**Série utilisée ici :** l'indice base 100 de la fenêtre commune (`metrics.normalized_indices`),
et non une richesse reconstituée à partir des rendements. Les deux donnent le même
résultat tant que les prix restent positifs.

**Cas limite à connaître :** le prix spot du WTI est négatif le 2020-04-20 (−36,98 USD).
L'indice base 100 passe alors sous 0 et le drawdown calculé vaut **−158,4 %**, ce qui est
mathématiquement correct mais ne décrit pas une perte finançable. Le notebook signale
explicitement cet artefact au lieu de le corriger silencieusement.

## 9. Corrélation

Calculer Pearson entre rendements appariés et alignés, puis indiquer le nombre d'observations communes. Les corrélations sont descriptives, peuvent varier dans le temps et ne prouvent pas de causalité.

## 10. Graphiques requis

- Prix bruts, en graphiques séparés.
- Indices normalisés base 100.
- Rendements quotidiens (ou à la fréquence choisie).
- Distributions des rendements.
- Volatilité glissante, si une fenêtre suffisamment documentée est retenue.
- Drawdown.
- Matrice de corrélation.

Tous les graphiques doivent comporter titre, axes, unités, légende, période et source.

## 11. Rendements non calculables

Un rendement simple est `NaN` dans deux cas documentés :

1. le prix précédent est non positif (WTI du 2020-04-20) — BR-005 et BR-014 ;
2. l'écart avec l'observation précédente dépasse **7 jours calendaires** — ce rendement
   ne représenterait plus la même unité de temps qu'une séance de marché.

Le logarithme suit la même règle de positivité (BR-006) et émet un `RuntimeWarning`
signalant le nombre de rendements indéfinis. Aucune valeur n'est inventée pour combler
ces trous ; les statistiques indiquent le nombre d'observations réellement utilisées
(1 494 pour le WTI, 1 495 pour les deux autres séries).

## 12. Limites d'interprétation

- WTI spot et contrats à terme ne sont pas équivalents.
- BTC/USD dépend du fournisseur et de l'heure de clôture.
- S&P 500 de prix n'inclut pas les dividendes.
- Les jours fériés et les calendriers diffèrent.
- Les résultats dépendent de la période choisie.
- Corrélation ne signifie pas causalité.
- Les données historiques peuvent être révisées ou soumises à des restrictions de réutilisation.
