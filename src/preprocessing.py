"""Validation, nettoyage et alignement des séries temporelles.

Ce module ne contacte jamais le réseau : il transforme des DataFrames déjà
récupérés (`date`, `close`) en un panel propre, trié, dédupliqué, restreint à
la période cible et aligné sur un calendrier commun.

Règles appliquées (voir `BUSINESS_RULES.md`) :

* BR-007 : dates parsées, tri croissant, doublons comptés avant toute suppression.
* BR-008 : aucune interpolation, aucun forward-fill.
* BR-009 : alignement par intersection des dates observées, règle documentée.
* BR-001 : filtrage inclusif des bornes de la période cible.

Toutes les fonctions sont pures et déterministes : elles sont testables avec des
fixtures synthétiques, sans accès à Internet.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ("date", "close")
EXTREME_MOVE_THRESHOLD = 0.20


class SchemaError(ValueError):
    """Structure de données inattendue (colonnes absentes, types invalides)."""


class EmptyDataError(ValueError):
    """Aucune observation disponible après filtrage ou alignement."""


def validate_schema(frame: pd.DataFrame, required: tuple[str, ...] = REQUIRED_COLUMNS) -> None:
    """Vérifie la présence des colonnes attendues et lève `SchemaError` sinon."""
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise SchemaError(
            f"Colonnes manquantes {missing} ; colonnes reçues : {list(frame.columns)}."
        )
    if frame.empty:
        raise EmptyDataError("Le DataFrame reçu ne contient aucune observation.")


def to_numeric_close(frame: pd.DataFrame, column: str = "close") -> pd.DataFrame:
    """Convertit la colonne de prix en float ; les valeurs illisibles deviennent NaN.

    Les marqueurs de valeur manquante documentés par les fournisseurs (chaîne
    vide, `.`, `NA`...) ne sont jamais remplacés par une valeur inventée.
    """
    raw = frame[column]
    cleaned = raw.astype("string").str.strip().replace({"": None, ".": None})
    numeric = pd.to_numeric(cleaned, errors="coerce").astype("float64")
    result = frame.copy()
    result[column] = numeric
    return result


def parse_dates(
    frame: pd.DataFrame, column: str = "date", *, errors: str = "raise"
) -> pd.DataFrame:
    """Convertit la colonne de dates en `datetime64[ns]`.

    `errors="raise"` (défaut) signale toute date non convertible ; `errors="coerce"`
    transforme les dates invalides en `NaT` pour permettre un audit ultérieur.
    Les timestamps aware sont convertis en UTC puis normalisés à la date du jour.
    """
    parsed = pd.to_datetime(frame[column], errors="coerce", utc=True)
    parsed = parsed.dt.tz_convert(None) if getattr(parsed.dtype, "tz", None) else parsed
    if errors == "raise" and parsed.isna().any():
        invalid = frame.loc[parsed.isna(), column].tolist()[:5]
        raise SchemaError(f"Dates non convertibles : {invalid}.")
    if errors != "raise":
        parsed = pd.to_datetime(frame[column], errors=errors, utc=True)
        parsed = parsed.dt.tz_convert(None) if getattr(parsed.dtype, "tz", None) else parsed
    else:
        parsed = parsed.dt.normalize()
    result = frame.copy()
    result[column] = parsed
    return result


def sort_by_date(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    """Trie les lignes par date croissante, de façon stable."""
    return frame.sort_values(column, kind="stable").reset_index(drop=True)


def find_duplicates(frame: pd.DataFrame, column: str = "date") -> list[pd.Timestamp]:
    """Retourne les dates apparaissant plusieurs fois, sans rien supprimer."""
    duplicated = frame[column][frame[column].duplicated(keep=False)]
    return sorted(pd.Timestamp(value) for value in duplicated.unique())


def drop_duplicate_dates(frame: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    """Supprime les dates dupliquées en conservant la dernière occurrence.

    Règle documentée (BR-007) : si un fournisseur renvoie deux lignes pour la
    même date, la plus récente du flux est retenue, car elle représente la
    version la plus à jour de la donnée.
    """
    if frame[column].duplicated().any():
        frame = frame.sort_values(column, kind="stable")
        frame = frame.drop_duplicates(subset=column, keep="last")
    return frame.reset_index(drop=True)


def observed_frequency_days(frame: pd.DataFrame, column: str = "date") -> float | None:
    """Retourne l'écart médian entre observations, en jours calendaires."""
    ordered = frame.sort_values(column)
    gaps = ordered[column].diff().dt.total_seconds().dropna() / 86400.0
    if gaps.empty:
        return None
    return float(gaps.median())


def max_gap_days(frame: pd.DataFrame, column: str = "date") -> float | None:
    """Retourne le plus grand écart entre deux observations consécutives (jours)."""
    ordered = frame.sort_values(column)
    gaps = ordered[column].diff().dt.total_seconds().dropna() / 86400.0
    if gaps.empty:
        return None
    return float(gaps.max())


def frame_gap_days(frame: pd.DataFrame, *, column: str = "date") -> pd.Series:
    """Retourne la distribution des écarts entre dates observations consécutives."""
    ordered = sort_by_date(frame, column)
    gaps = ordered[column].diff().dt.total_seconds().dropna() / 86400.0
    return gaps.astype("int64")


def audit_quality(frame: pd.DataFrame, *, column: str = "date") -> dict[str, Any]:
    """Construit le rapport qualité d'une série brute (cf. `DATA_QUALITY.md`).

    Le rapport ne modifie rien : il signale. Les variations extrêmes ne sont ni
    supprimées ni corrigées, elles sont seulement dénombrées.
    """
    validate_schema(frame)
    ordered = sort_by_date(frame, column)
    dates = ordered[column]
    closes = ordered["close"]
    valid = closes.dropna()
    duplicates = find_duplicates(ordered, column)
    non_finite = int((~np.isfinite(valid.to_numpy(dtype="float64"))).sum())
    non_positive = int((valid <= 0).sum())
    moves = valid.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    extreme_mask = moves.abs() > EXTREME_MOVE_THRESHOLD
    return {
        "rows": int(len(ordered)),
        "first_date": None if ordered.empty else dates.min().date().isoformat(),
        "last_date": None if ordered.empty else dates.max().date().isoformat(),
        "duplicate_dates": len(duplicates),
        "duplicate_examples": [value.date().isoformat() for value in duplicates[:5]],
        "missing_close": int(closes.isna().sum()),
        "missing_close_pct": float(closes.isna().mean() * 100.0),
        "non_finite": non_finite,
        "non_positive": non_positive,
        "observed_gap_days_median": observed_frequency_days(ordered, column),
        "observed_gap_days_max": max_gap_days(ordered, column),
        "moves_over_threshold": int(extreme_mask.sum()),
        "extreme_move_threshold": EXTREME_MOVE_THRESHOLD,
        "largest_move": None if moves.empty else float(moves.abs().max()),
        "min_close": None if valid.empty else float(valid.min()),
        "max_close": None if valid.empty else float(valid.max()),
        "last_close": None if valid.empty else float(valid.iloc[-1]),
    }


def select_period(
    frame: pd.DataFrame, start: date | str, end: date | str, *, column: str = "date"
) -> pd.DataFrame:
    """Filtre la période `[start, end]` **bornes incluses** (BR-001)."""
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    mask = frame[column].between(start_ts, end_ts, inclusive="both")
    return frame.loc[mask].reset_index(drop=True)


def align_common_dates(
    frames: dict[str, pd.DataFrame], *, column: str = "date", value: str = "close"
) -> pd.DataFrame:
    """Aligne plusieurs séries sur l'intersection de leurs dates observées.

    Principe (BR-008, BR-009) : aucune valeur n'est interpolée ni reconduite.
    Une date absente d'une série exclut simplement cette date du panel commun.
    Les dates retenues sont triées ; le panel est renvoyé sans `NaN`.
    """
    if not frames:
        raise SchemaError("Aucun cadre de données fourni à aligner.")
    sets = []
    for asset, frame in frames.items():
        validate_schema(frame)
        if frame[column].duplicated().any():
            raise SchemaError(
                f"Doublons de date présents dans {asset} : aligner des séries "
                "dédupliquées uniquement."
            )
        sets.append(set(frame[column]))
    common = sorted(set.intersection(*sets))
    if not common:
        raise EmptyDataError(
            "Aucune date commune aux séries fournies : la période ou les sources "
            "doivent être revues avant tout calcul comparatif."
        )
    pieces = []
    for asset, frame in frames.items():
        indexed = frame.set_index(column)[value]
        pieces.append(indexed.reindex(common).rename(asset))
    panel = pd.concat(pieces, axis=1)
    panel.index.name = column
    return panel


def alignment_report(
    frames: dict[str, pd.DataFrame], panel: pd.DataFrame, *, column: str = "date"
) -> dict[str, Any]:
    """Compare le nombre d'observations avant et après alignement (DATA_QUALITY §9)."""
    before = {asset: int(len(frame)) for asset, frame in frames.items()}
    after = int(len(panel))
    losses = {asset: before[asset] - after for asset in frames}
    return {
        "observations_before": before,
        "observations_aligned": after,
        "observations_lost": losses,
        "first_aligned_date": panel.index.min().date().isoformat(),
        "last_aligned_date": panel.index.max().date().isoformat(),
        "column": column,
    }


def resample_weekly(
    frame: pd.DataFrame, *, column: str = "date", value: str = "close"
) -> pd.DataFrame:
    """Agrège une série en observation hebdomadaire (dernière observation de la semaine).

    Variante de sensibilité (ADR-002) : la semaine ISO est fermée par la
    dernière date réellement observée dans cette semaine. Aucune valeur n'est
    inventée pour les semaines sans observation. Le résultat conserve une
    unique colonne `close`, comme les autres fonctions de ce module.
    """
    ordered = sort_by_date(frame, column).set_index(column)
    if ordered.empty:
        return pd.DataFrame(columns=["close"], index=ordered.index)
    iso_week = ordered.index.isocalendar()
    keys = pd.Index(
        [
            pd.Timestamp.fromisocalendar(int(year), int(week), 7)
            for year, week in zip(iso_week["year"], iso_week["week"], strict=True)
        ],
        name="week_end",
    )
    weekly = ordered.set_axis(keys).groupby(level=0).last()
    selected = weekly[[value]] if value in weekly.columns else weekly.iloc[:, :1]
    selected = selected.copy()
    selected.columns = ["close"]
    selected.index.name = "week_end"
    return selected


def pivot_long(
    panel: pd.DataFrame, *, index_name: str = "date", value_name: str = "close"
) -> pd.DataFrame:
    """Transforme un panel large (une colonne par actif) en format long.

    Utile pour l'export et les contrôles qualité ; le panel reste la structure
    de travail principale.
    """
    long = panel.rename_axis(index_name).stack().reset_index()
    long.columns = [index_name, "asset", value_name]
    long["asset"] = long["asset"].astype("string")
    return long


def assert_positive(series: pd.Series, *, name: str = "série") -> None:
    """Lève une erreur si la série contient des prix nuls, négatifs ou non finis."""
    values = pd.to_numeric(series, errors="coerce").astype("float64")
    invalid = values[~np.isfinite(values) | (values <= 0)]
    if not invalid.empty:
        raise SchemaError(
            f"{name} : {len(invalid)} prix non finis ou non positifs "
            f"(exemples : {invalid.head(5).tolist()}). Corriger la source avant calcul."
        )
