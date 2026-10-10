# Critères d'acceptation

État au 2026-10-10, après exécution réelle du projet. Les critères non satisfaits sont
laissés explicitement ouverts.

## Données
- [x] Les trois séries ont un fournisseur et un identifiant précis (`DATA_SOURCES.md`,
      registre `src.data_loader.SERIES`).
- [x] URL, unités, fréquence, définition des prix et conditions de réutilisation sont
      documentées. **Réserve :** les CGU FRED et Coinbase n'ont pas pu être lues depuis
      cet environnement, elles sont signalées comme non vérifiées.
- [x] La période réellement disponible est vérifiée : `2020-01-02` → `2025-12-31` pour
      le panel commun, chaque série étant couverte dès `2020-01-01` ou `2020-01-02`.
- [x] Les dates sont triées et les doublons détectés (0 doublon sur les trois séries).
- [x] Les valeurs manquantes et non finies sont quantifiées (WTI 65, SP500 57, BTC 0).
- [x] L'alignement des calendriers est décrit, justifié et chiffré (1 496 dates
      communes ; pertes : WTI 4, SP500 12, BTC 689).
- [x] Les échecs de récupération ne déclenchent pas de données de secours fictives
      (test `test_network_failure_never_returns_fabricated_data`, et échec réel du
      pipeline en cas de coupure, sans substitution).

## Calculs
- [x] La normalisation base 100 est testée sur un exemple connu (`[10, 20, 15]`).
- [x] Les rendements simples sont testés sur des prix synthétiques (`[100, 110]` → `0,10`).
- [x] Les rendements logarithmiques excluent les prix non positifs (`NaN` + avertissement,
      ou exception avec `on_invalid="raise"`).
- [x] La volatilité précise sa convention d'annualisation (`N = 252` sur le panel
      aligné, `N = 365` affiché à titre informatif).
- [x] Le drawdown est validé sur une série à sommet et baisse connus (−20 %).
- [x] Les corrélations utilisent les rendements alignés et affichent le nombre
      d'observations (1 494 dates appariées complètes).

## Notebook et documentation
- [x] Toutes les cellules s'exécutent du début à la fin dans l'environnement documenté
      (exécution réelle : 47 cellules, 0 erreur).
- [x] Les graphiques ont titres, axes, unités, légendes, période et source (9 figures).
- [x] Les conclusions sont soutenues par des valeurs réellement calculées (section 14
      générée à partir des résultats du run).
- [x] Les limites sont exposées : calendriers, clôtures non simultanées, indice de prix
      sans dividendes, prix spot négatif du WTI, absence de causalité.
- [x] README et instructions d'installation suffisent à un autre utilisateur.
- [x] Aucun secret ni fichier interdit n'est versionné (`data/raw/`, `data/processed/`,
      `outputs/figures/`, `.env` sont ignorés par Git).

## Qualité
- [x] Les tests automatisés passent : `python -m pytest` → **86 passed**.
- [x] Qualité statique : `ruff check .` → *All checks passed!*, `ruff format --check .`
      → 31 fichiers conformes.
- [x] Les erreurs de source et les données indisponibles sont signalées.
- [x] Aucun test n'est déclaré réussi sans avoir été exécuté.

## Critères ouverts (non satisfaits)
- [ ] **Licences vérifiées.** Les conditions d'utilisation de FRED et de Coinbase doivent
      être lues avant toute publication des données brutes (page FRED injoignable depuis
      cet environnement).
- [ ] **Jupyter complet non installé.** L'exécution du notebook a été réalisée avec
      `nbclient` + `ipykernel` (47 cellules, 0 erreur, 9 figures) ; l'interface
      `jupyter notebook` reste à vérifier sur la machine cible.
- [ ] **Sensibilité à la fenêtre.** L'analyse de sensibilité porte sur la fréquence
      (hebdomadaire) mais pas sur la date de début.
- [ ] **Intégration réseau automatisée.** Les tests d'intégration existent uniquement
      comme procédure manuelle documentée.