# ADR-002 — Prétraitement et alignement des séries

- **Statut :** accepté (2026-10-10).
- **Contexte :** Bitcoin cote 7j/7, les marchés américains ont leurs jours fériés et
  leurs jours ouvrés ; les trois sources n'utilisent pas la même clôture.
- **Décision principale :** l'analyse comparative se fait sur l'**intersection des dates
  observées** des trois séries, sans forward-fill, sans interpolation et sans suppression
  d'outlier. La base 100 est la première observation valide de cette fenêtre commune.
- **Options comparées :**
  - *intersection quotidienne* : simple, lisible, mais elle retire les dates où une série
    manque et sélectionne de fait les séances communes aux trois marchés ;
  - *agrégation hebdomadaire* : moins sensible au bruit quotidien, mais elle suppose une
    règle de clôture hebdomadaire et masque les mouvements intra-semaine.
- **Traitement retenu :** l'intersection quotidienne est l'analyse principale ; la
  fréquence hebdomadaire est calculée en **analyse de sensibilité** dans le notebook
  (ADR-002 §"Conséquences"), avec la dernière observation observée de chaque semaine ISO
  comme valeur hebdomadaire.
- **Motifs :**.reduce les hypothèses cachées, rend l'effet de l'alignement visible
  (le rapport qualité publie le nombre d'observations avant et après) et évite tout
  comblement artificiel.
- **Conséquences :** les rendements d'une même date ne portent pas sur le même instant
  (clôture américaine contre minuit UTC) ; la comparaison est descriptive et imparfaite.
  Un rendement couvrant plus de 7 jours de calendrier est mis à `NaN` dans la série
  quotidienne, car il ne représente plus la même unité de temps.
- **Point restant à valider :** une analyse de sensibilité sur la date de début de la
  fenêtre serait pertinente, elle n'est pas encore implémentée.