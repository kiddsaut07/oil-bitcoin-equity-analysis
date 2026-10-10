# ADR-003 — Accès réseau et robustesse de la récupération

- **Statut :** accepté (2026-10-10).
- **Contexte :** depuis l'environnement du projet, l'accès à `fred.stlouisfed.org` est
  instable : certaines requêtes aboutissent en quelques secondes, d'autres expirent au
  bout de 60 s. Le diagnostic a montré que la connexion TLS aboutit, mais que le serveur
  (CDN) ne répond **que** si le client propose ALPN avec HTTP/2 : `urllib` (bibliothèque
  standard) et `httpx` restent bloqués en lecture dans cette configuration, alors que
  `curl` répond.
- **Décision :** la couche HTTP est explicite et interchangeable (`src/data_loader.py`) :
  - `curl_transport` : exécutable `curl`, utilisé en premier s'il est présent ;
  - `urllib_transport` : bibliothèque standard, filet de sécurité, délai borné à 30 s ;
  - `http_get_bytes` : boucle de reprise (délai croissant, respect de `Retry-After`),
    erreur HTTP 4xx définitive non retentée, `DataSourceError` explicite en cas d'échec.
- **Motifs :** respecter BR-015 (échec explicite, aucune donnée de remplacement) tout en
  gardant la possibilité de récupérer réellement les données sur un réseau dégradé,
  sans dépendance supplémentaire à installer.
- **Conséquences :** `curl` devient une dépendance d'exécution légère (présent par défaut
  sur Linux et macOS). Les tests n'utilisent aucun transport réel : un transport factice
  est injecté. Les paramètres `--retries` et `--timeout` du pipeline permettent
  d'adapter la patience au réseau du moment.
- **Point restant à valider :** sur un réseau sain, `urllib` seul suffirait ; ce choix
  est un compromis lié à l'environnement de développement, pas une propriété des sources.