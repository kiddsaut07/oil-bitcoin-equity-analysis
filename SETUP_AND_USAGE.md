# Installation et utilisation

## Prérequis vérifiés

| Élément | Exigence | État sur la machine de développement |
|---|---|---|
| Python | ≥ 3.11 (`pyproject.toml`) | **3.13.12** — testé |
| pandas | ≥ 2.1, < 3.0 | **2.3.3** — testé |
| NumPy | ≥ 1.26, < 3.0 | **2.2.4** — testé |
| Matplotlib | ≥ 3.8, < 4.0 | **3.10.1** — testé |
| pytest | ≥ 8.0, < 9.0 | **8.4.2** — testé |
| Jupyter / noyau | jupyter ≥ 1.0 | `ipykernel` 7.4.0 — testé pour l'exécution du notebook |
| Ruff | ≥ 0.6, < 1.0 | **0.17.0** — `ruff check .` et `ruff format --check .` passent |
| `curl` | présent sur le `PATH` | utilisé par le transport HTTP |
| Accès Internet | nécessaire au téléchargement | FRED et Coinbase sont **instables** : prévoir des reprises |

Le poste de développement étant quasi saturé en espace disque, l'environnement
virtuel a été créé avec `--system-site-packages` afin de réutiliser pandas, NumPy et
Matplotlib déjà présents :

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Installation classique (machine avec de la place) :

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows PowerShell : remplacer `source .venv/bin/activate` par `.venv\Scripts\Activate.ps1`.

## Variables d'environnement

Aucune clé API n'est nécessaire avec les sources retenues. `.env` n'est donc pas utilisé
et reste ignoré par Git.

Deux variables optionnelles existent :

| Variable | Effet |
|---|---|
| `OBAE_USER_AGENT` | impose un en-tête `User-Agent`. **À laisser vide** : le CDN de FRED réinitialise les connexions quand un agent personnalisé est envoyé (mesuré : 0 succès sur 13 avec `-A`, 8 sur 8 sans). |
| `OBAE_*` / clés fournisseurs | non utilisées ; le projet ne demande ni compte ni clé. |

## Préparer les données

```bash
python -m src.pipeline --start 2020-01-01 --end 2025-12-31
```

Options utiles :

| Option | Effet |
|---|---|
| `--start` / `--end` | bornes incluses de la période (format `AAAA-MM-JJ`) |
| `--offline` | réutilise `data/raw/*.csv` sans réseau |
| `--assets WTI SP500` | ne traite qu'un sous-ensemble de séries |
| `--retries 10 --timeout 40` | patience sur un réseau instable |
| `--help` | liste des options |

En cas d'échec réseau, le message indique la source, l'URL, le nombre de tentatives et
les erreurs observées. **Aucune donnée fictive ne remplace jamais les données réelles**
(BR-015) : le pipeline s'arrête.

Fichiers produits :

- `data/raw/{asset}.csv` et `data/raw/{asset}_metadata.json` (traçabilité) ;
- `data/processed/prices_aligned.csv`, `indices_base100.csv`, `returns_simple.csv`,
  `returns_log.csv`, `drawdowns.csv`, `quality_report.json`.

Ces dossiers sont ignorés par Git (`data/raw/*`, `data/processed/*`) : les données ne
sont pas publiables tant que les conditions des fournisseurs n'ont pas été vérifiées.

## Lancer le notebook

```bash
jupyter notebook
```

Ouvrir `notebooks/oil_bitcoin_equity_analysis.ipynb`, puis **Restart Kernel and Run All
Cells`. Le notebook appelle les fonctions de `src/` ; il ne recalcule rien à la main.
Il détecte la présence de `data/raw/` : si le réseau échoue et que des copies locales
sont disponibles, il le signale dans la sortie et bascule en mode hors ligne.

Exécution non interactive (utilisée pour le contrôle final) :

```bash
python - <<'EOF'
import nbformat
from nbclient import NotebookClient
nb = nbformat.read("notebooks/oil_bitcoin_equity_analysis.ipynb", as_version=4)
NotebookClient(nb, timeout=1800, kernel_name="python3",
               resources={"metadata": {"path": "notebooks/"}}).execute()
nbformat.write(nb, "notebooks/oil_bitcoin_equity_analysis.ipynb")
EOF
```

## Tests et qualité

```bash
python -m pytest            # 86 tests, sans accès réseau
ruff check .                # si ruff est installé
ruff format --check .
```

Résultat réel de la dernière exécution :

```text
$ python -m pytest -q
86 passed

$ ruff check .
All checks passed!

$ ruff format --check .
31 files already formatted
```

`pyproject.toml` exclut `notebooks/*.ipynb` des règles `E402` (import après
`sys.path`) et `E501` (longueur des cellules markdown).

## Reproductibilité

À consigner pour une reproduction exacte :

- version Python (`3.13.12`) et versions de bibliothèques ;
- date et heure de collecte, présentes dans `data/raw/{asset}_metadata.json` (`retrieved_at`) ;
- paramètres de période, d'alignement et d'annualisation, dans
  `data/processed/quality_report.json` ;
- fournisseurs et identifiants dans `DATA_SOURCES.md`.

Les fournisseurs peuvent réviser leurs séries ou modifier leurs API ; une reproduction
exacte n'est pas garantie sans copie autorisée des données d'origine.