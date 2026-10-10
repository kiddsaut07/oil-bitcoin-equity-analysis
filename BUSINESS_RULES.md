# Règles de gestion et règles analytiques

Ces règles sont normatives pour l'implémentation, sauf mention « à valider ».

- **BR-001 — Période cible :** période initiale du 2020-01-01 au 2025-12-31 inclus. Le rapport doit afficher les dates réellement disponibles et ne jamais prétendre que toute la période est couverte sans vérification.
- **BR-002 — Source explicite :** chaque série possède un fournisseur, un identifiant, une unité, une devise, une fréquence et une définition documentés.
- **BR-003 — Prix bruts :** ne pas comparer directement les niveaux numériques des trois séries comme s'ils avaient la même unité.
- **BR-004 — Base 100 :** pour chaque série, l'indice vaut `prix_t / prix_base * 100`. La date et la valeur de base sont affichées. La base est la première observation valide de la fenêtre commune selon la règle de calendrier approuvée.
- **BR-005 — Rendement simple :** `r_t = P_t / P_(t-1) - 1`, uniquement pour des prix valides et un intervalle temporel admissible.
- **BR-006 — Rendement logarithmique :** `ln(P_t / P_(t-1))` n'est calculé que si les deux prix sont strictement positifs.
- **BR-007 — Dates et ordre :** les dates sont parsées, triées par ordre croissant et les doublons sont signalés avant toute déduplication.
- **BR-008 — Valeurs manquantes :** ne pas interpoler ni forward-fill les prix par défaut. Tout traitement alternatif doit être justifié et testé.
- **BR-009 — Calendriers :** Bitcoin fonctionne 7 jours sur 7 alors que les marchés actions et matières premières ont des calendriers distincts. Le mode d'alignement (dates exactes ou agrégation hebdomadaire) doit être documenté et cohérent.
- **BR-010 — Clôture quotidienne :** les définitions et fuseaux horaires des clôtures doivent être documentés. Ne pas supposer que des observations portant la même date représentent exactement le même instant.
- **BR-011 — Volatilité :** distinguer l'écart-type des rendements observés de la volatilité annualisée. Toute annualisation précise la convention retenue et ses hypothèses.
- **BR-012 — Corrélation :** calculer Pearson sur les rendements alignés, jamais par défaut sur les prix bruts. Rapporter le nombre d'observations communes.
- **BR-013 — Drawdown :** calculer la baisse relative depuis le précédent sommet de la série de valeur normalisée ou de richesse construite à partir des rendements, en expliquant la convention.
- **BR-014 — Données négatives ou nulles :** les prix nuls/négatifs et valeurs non finies doivent être signalés et traités selon la formule concernée ; ne pas appliquer les logarithmes à des valeurs non positives.
- **BR-015 — Échec réseau :** un téléchargement raté doit produire un message d'erreur explicite. Aucune donnée synthétique ne peut se substituer silencieusement aux données réelles.
- **BR-016 — Traçabilité :** les tableaux et figures indiquent la source et la période. Les paramètres de récupération et la date de collecte sont enregistrés.
- **BR-017 — Causalité :** corrélation et coïncidence temporelle ne prouvent pas une causalité.
- **BR-018 — S&P 500 :** si la série choisie est l'indice de prix `SP500`, signaler que les dividendes ne sont pas inclus.
- **BR-019 — Reproductibilité :** conserver les paramètres et versions logicielles ; ne pas prétendre à une reproduction exacte si le fournisseur révise les données ou si les données brutes ne peuvent être redistribuées.
- **BR-020 — Données de test :** les fixtures synthétiques sont exclusivement utilisées pour tester. Elles ne sont jamais mélangées aux données historiques dans les résultats finaux.
