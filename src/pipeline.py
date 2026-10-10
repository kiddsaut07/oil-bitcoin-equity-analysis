"""Orchestration du pipeline : acquisition → qualité → alignement → métriques.

Ce module ne contient pas de calcul statistique nouveau : il appelle les
fonctions de `data_loader`, `preprocessing` et `metrics` dans l'ordre défini
par `TECHNICAL_DESIGN.md`, écrit les fichiers de traçabilité et renvoie un objet
`PipelineResult` exploitable par le notebook.

Utilisation en ligne de commande :

```bash
python -m src.pipeline --start 2020-01-01 --end 2025-12-31
python -m src.pipeline --offline   # réutilise data/raw/ sans accès réseau
```

Aucune donnée n'est fabriquée : si une source est injoignable, l'exécution
s'interrompt avec un message explicite (BR-015).
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from src import data_loader, metrics, preprocessing

DEFAULT_START = "2020-01-01"
DEFAULT_END = "2025-12-31"
DEFAULT_ASSETS = ("WTI", "BTC_USD", "SP500")
PERIODS_PER_YEAR = metrics.TRADING_DAYS_PER_YEAR
BITCOIN_PERIODS_PER_YEAR = metrics.BITCOIN_DAYS_PER_YEAR
ROLLING_WINDOW = metrics.DEFAULT_ROLLING_WINDOW
MAX_RETURN_GAP_DAYS = metrics.DEFAULT_RETURN_GAP_DAYS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"


@dataclass
class PipelineResult:
    """Ensemble des objets produits par une exécution complète du pipeline."""

    prices: pd.DataFrame
    indices: pd.DataFrame
    returns: pd.DataFrame
    log_returns: pd.DataFrame
    drawdowns: pd.DataFrame
    rolling_volatility: pd.DataFrame
    metadata: dict[str, dict[str, Any]] = field(default_factory=dict)
    quality: dict[str, dict[str, Any]] = field(default_factory=dict)
    alignment: dict[str, Any] = field(default_factory=dict)
    bases: dict[str, dict[str, Any]] = field(default_factory=dict)
    alignment_raw: dict[str, pd.DataFrame] = field(default_factory=dict)
    alignment_gaps: dict[str, pd.Series] = field(default_factory=dict)
    start: str = DEFAULT_START
    end: str = DEFAULT_END
    raw_observations: dict[str, int] = field(default_factory=dict)


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    """Écrit un fichier JSON lisible (traçabilité, DATA_QUALITY §10)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    return path


def _clean_series(raw: pd.DataFrame) -> pd.DataFrame:
    """Applique le schéma, le parsing des dates et le tri, sans encore dédupliquer.

    La déduplication intervient après l'audit : `DATA_QUALITY.md` exige de
    compter les doublons avant de décider quoi en faire (BR-007).
    """
    frame = raw.copy()
    frame = preprocessing.to_numeric_close(frame)
    frame = preprocessing.parse_dates(frame)
    return preprocessing.sort_by_date(frame)


def _load_cached(asset: str, raw_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Relit une copie locale autorisée de `data/raw/{asset}.csv` (mode `--offline`)."""
    path = raw_dir / f"{asset}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Aucune copie locale de {asset} dans {raw_dir}. "
            "Relancer une fois sans --offline pour télécharger les données."
        )
    frame = pd.read_csv(path, parse_dates=["date"])
    metadata_path = raw_dir / f"{asset}_metadata.json"
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        metadata = dict(data_loader.describe_series(asset))
        metadata.update(
            {
                "retrieved_at": None,
                "source": "copie locale",
                "request_endpoint": None,
                "request_params": None,
            }
        )
    return frame, metadata


def run_pipeline(
    start: str = DEFAULT_START,
    end: str = DEFAULT_END,
    *,
    assets: tuple[str, ...] = DEFAULT_ASSETS,
    raw_dir: Path = RAW_DIR,
    processed_dir: Path = PROCESSED_DIR,
    offline: bool = False,
    retries: int = data_loader.DEFAULT_RETRIES,
    timeout: int = data_loader.DEFAULT_TIMEOUT,
) -> PipelineResult:
    """Exécute le pipeline complet et écrit les artefacts de traçabilité.

    Étapes : chargement de la configuration, téléchargement, métadonnées,
    contrôle de schéma, audit qualité, filtrage de période, analyse des
    calendriers, alignement, calculs de base (BR-004 à BR-013).
    """
    pd.Timestamp(start), pd.Timestamp(end)
    if pd.Timestamp(start) > pd.Timestamp(end):
        raise ValueError(f"Période invalide : début {start} postérieur à la fin {end}.")

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    cleaned: dict[str, pd.DataFrame] = {}
    metadata: dict[str, dict[str, Any]] = {}
    quality: dict[str, dict[str, Any]] = {}
    raw_observations: dict[str, int] = {}

    for asset in assets:
        if offline:
            raw, meta = _load_cached(asset, raw_dir)
        else:
            raw, meta = data_loader.fetch_series(
                asset, start, end, retries=retries, timeout=timeout
            )
        raw.to_csv(raw_dir / f"{asset}.csv", index=False)
        _write_json(raw_dir / f"{asset}_metadata.json", meta)
        raw_observations[asset] = int(len(raw))

        frame = _clean_series(raw)
        window = preprocessing.select_period(frame, start, end)
        report = preprocessing.audit_quality(frame)
        report.update(
            {
                "provider": meta.get("provider"),
                "series_id": meta.get("series_id"),
                "unit": meta.get("unit"),
                "currency": meta.get("currency"),
                "retrieved_at": meta.get("retrieved_at"),
                "excluded_by_period_filter": int(len(frame) - len(window)),
                "dropped_missing_in_window": int(window["close"].isna().sum()),
            }
        )
        metadata[asset] = meta
        quality[asset] = report
        cleaned[asset] = preprocessing.drop_duplicate_dates(frame)

    in_window = {asset: _period_filter(frame, start, end) for asset, frame in cleaned.items()}
    panel = preprocessing.align_common_dates(in_window)
    alignment = preprocessing.alignment_report(in_window, panel)
    gaps = {asset: preprocessing.frame_gap_days(frame) for asset, frame in in_window.items()}

    indices, bases = metrics.normalized_indices(panel)
    returns = panel.apply(
        lambda column: metrics.simple_returns(
            column, max_gap_days=MAX_RETURN_GAP_DAYS, name=str(column)
        )
    )
    log_returns = panel.apply(
        lambda column: metrics.log_returns(column, on_invalid="nan", name=str(column))
    )
    drawdowns = indices.apply(metrics.drawdown_series)
    rolling = returns.apply(
        lambda column: metrics.rolling_volatility(
            column, window=ROLLING_WINDOW, periods_per_year=PERIODS_PER_YEAR
        )
    )

    panel.to_csv(processed_dir / "prices_aligned.csv", index_label="date")
    indices.to_csv(processed_dir / "indices_base100.csv", index_label="date")
    returns.to_csv(processed_dir / "returns_simple.csv", index_label="date")
    log_returns.to_csv(processed_dir / "returns_log.csv", index_label="date")
    drawdowns.to_csv(processed_dir / "drawdowns.csv", index_label="date")

    report = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "study_window": {"start": start, "end": end, "bounds": "incluses"},
        "periods_per_year": PERIODS_PER_YEAR,
        "bitcoin_periods_per_year": BITCOIN_PERIODS_PER_YEAR,
        "max_return_gap_days": MAX_RETURN_GAP_DAYS,
        "rolling_window": ROLLING_WINDOW,
        "quality": quality,
        "alignment": alignment,
        "raw_observations": raw_observations,
    }
    _write_json(processed_dir / "quality_report.json", report)

    return PipelineResult(
        prices=panel,
        indices=indices,
        returns=returns,
        log_returns=log_returns,
        drawdowns=drawdowns,
        rolling_volatility=rolling,
        metadata=metadata,
        quality=quality,
        alignment=alignment,
        bases=bases,
        alignment_raw=in_window,
        alignment_gaps=gaps,
        start=start,
        end=end,
        raw_observations=raw_observations,
    )


def _period_filter(frame: pd.DataFrame, start: str, end: str) -> pd.DataFrame:
    """Filtre la période cible, bornes incluses, sans supprimer de valeurs manquantes."""
    filtered = preprocessing.select_period(frame, start, end)
    return filtered.dropna(subset=["close"]).reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    """Point d'entrée en ligne de commande."""
    parser = argparse.ArgumentParser(description="Pipeline Oil / Bitcoin / S&P 500")
    parser.add_argument("--start", default=DEFAULT_START, help="Date de début (incluse)")
    parser.add_argument("--end", default=DEFAULT_END, help="Date de fin (incluse)")
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Réutiliser les copies locales de data/raw/ sans accès réseau",
    )
    parser.add_argument(
        "--retries", type=int, default=data_loader.DEFAULT_RETRIES, help="Nombre de tentatives HTTP"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=data_loader.DEFAULT_TIMEOUT,
        help="Délai maximal par requête (s)",
    )
    parser.add_argument(
        "--assets",
        nargs="+",
        default=list(DEFAULT_ASSETS),
        help="Sous-ensemble de séries à traiter",
    )
    args = parser.parse_args(argv)
    result = run_pipeline(
        start=args.start,
        end=args.end,
        assets=tuple(args.assets),
        offline=args.offline,
        retries=args.retries,
        timeout=args.timeout,
    )
    print(
        f"Période alignée : {result.alignment['first_aligned_date']} → "
        f"{result.alignment['last_aligned_date']}"
    )
    print(f"Observations alignées : {result.alignment['observations_aligned']}")
    print(f"Prix conservés : {len(result.prices)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
