"""Métriques statistiques : normalisation, rendements, risque et corrélation.

Toutes les fonctions sont pures, vectorisées et sans accès réseau, afin d'être
testées sur des séries synthétiques (`tests/`).

Conventions retenues et documentées (`METHODOLOGY.md`, `BUSINESS_RULES.md`) :

* BR-004 : indice base 100 = `prix_t / prix_base * 100`, base = première
  observation valide de la fenêtre commune.
* BR-005 : rendement simple = `P_t / P_{t-1} - 1`, calculé uniquement sur des
  prix valides et un intervalle de temps admissible.
* BR-006 : rendement logarithmique = `ln(P_t / P_{t-1})`, uniquement si les
  deux prix sont strictement positifs.
* BR-011 : l'écart-type des rendements observés est distinct de la volatilité
  annualisée `std * sqrt(N)` ; `N` est toujours explicité par l'appelant.
* BR-012 : la corrélation de Pearson porte sur des rendements alignés, jamais
  sur les niveaux de prix.
"""

from __future__ import annotations

import math
import warnings
from typing import Any

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
BITCOIN_DAYS_PER_YEAR = 365
DEFAULT_RETURN_GAP_DAYS = 7.0
DEFAULT_ROLLING_WINDOW = 30


def _check_prices(prices: pd.Series, *, name: str) -> pd.Series:
    """Vérifie qu'une série de prix est exploitable (vide, NaN, non positif)."""
    numeric = pd.to_numeric(prices, errors="coerce").astype("float64")
    if numeric.empty:
        raise ValueError(f"{name} : série de prix vide, aucun calcul possible.")
    invalid = numeric[~np.isfinite(numeric)]
    if not invalid.empty:
        raise ValueError(
            f"{name} : {len(invalid)} prix non finis ; nettoyer la source avant calcul."
        )
    return numeric


def normalize_base_100(
    prices: pd.Series, *, name: str = "série"
) -> tuple[pd.Series, float, pd.Timestamp]:
    """Normalise une série de prix en indice base 100.

    Retourne `(indice, valeur_de_base, date_de_base)`. La base est la première
    observation non nulle et positive ; une série commençant par un prix négatif
    ou nul est rejetée plutôt que normalisée.
    """
    numeric = _check_prices(prices, name=name)
    base_value = float(numeric.iloc[0])
    if base_value <= 0:
        raise ValueError(
            f"{name} : prix de base {base_value} non positif, la normalisation base 100 "
            "est impossible pour cette fenêtre."
        )
    index = numeric / base_value * 100.0
    base_date = pd.Timestamp(prices.index[0])
    return index, base_value, base_date


def simple_returns(
    prices: pd.Series,
    *,
    max_gap_days: float | None = DEFAULT_RETURN_GAP_DAYS,
    name: str = "série",
) -> pd.Series:
    """Calcule les rendements simples `P_t / P_{t-1} - 1` (BR-005).

    Un rendement est noté `NaN` si le prix précédent est non positif, ou si
    l'écart temporel dépasse `max_gap_days` : un intervalle plus long ne
    représente pas la même unité de temps qu'un rendement quotidien.
    """
    numeric = _check_prices(prices, name=name)
    returns = numeric.pct_change()
    invalid_base = (numeric.shift(1) <= 0) | ~np.isfinite(numeric.shift(1))
    returns = returns.mask(invalid_base)
    if max_gap_days is not None:
        gaps = pd.Series(prices.index, index=prices.index).diff().dt.total_seconds() / 86400.0
        returns = returns.mask(gaps > max_gap_days)
    return returns


def log_returns(
    prices: pd.Series,
    *,
    on_invalid: str = "nan",
    name: str = "série",
) -> pd.Series:
    """Calcule les rendements logarithmiques `ln(P_t / P_{t-1})` (BR-006).

    Les prix non strictement positifs rendent le logarithme indéfini. Avec
    `on_invalid="nan"` ils produisent `NaN` et un avertissement ; avec
    `on_invalid="raise"` une erreur est levée.
    """
    numeric = _check_prices(prices, name=name)
    previous = numeric.shift(1)
    has_previous = previous.notna()
    valid = has_previous & (numeric > 0) & (previous > 0)
    returns = pd.Series(np.nan, index=prices.index, dtype="float64")
    returns.loc[valid] = np.log(numeric.loc[valid] / previous.loc[valid])
    invalid_count = int(((~valid) & has_previous).sum())
    if invalid_count and on_invalid == "raise":
        raise ValueError(
            f"{name} : {invalid_count} rendements logarithmiques indéfinis "
            "(prix non strictement positif)."
        )
    if invalid_count:
        warnings.warn(
            f"{name} : {invalid_count} rendement(s) logarithmique(s) non définis, "
            "remplacés par NaN (prix non strictement positif).",
            RuntimeWarning,
            stacklevel=2,
        )
    return returns


def sample_std(values: pd.Series) -> float:
    """Écart-type d'échantillon (ddof=1), convention utilisée partout ici."""
    numeric = pd.to_numeric(values, errors="coerce").astype("float64").dropna()
    if numeric.size < 2:
        raise ValueError("Il faut au moins deux observations pour un écart-type.")
    return float(numeric.std(ddof=1))


def annualized_volatility(
    returns: pd.Series,
    *,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
    name: str = "série",
) -> float:
    """Volatilité annualisée : `std(returns) * sqrt(N)` (BR-011).

    `periods_per_year` doit refléter la fréquence **effective de la série
    analysée** : 252 pour un panel de séances de marchés traditionnels, 365 pour
    une série Bitcoin quotidienne isolée. Comparer des séries sans préciser `N`
    rendrait la comparaison trompeuse.
    """
    if periods_per_year <= 0:
        raise ValueError("periods_per_year doit être strictement positif.")
    return sample_std(returns) * math.sqrt(periods_per_year)


def rolling_volatility(
    returns: pd.Series,
    *,
    window: int = DEFAULT_ROLLING_WINDOW,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
) -> pd.Series:
    """Volatilité annualisée en fenêtre glissante (écart-type d'échantillon)."""
    if window < 2:
        raise ValueError("La fenêtre de volatilité doit contenir au moins deux observations.")
    rolling_std = returns.rolling(window=window, min_periods=window).std(ddof=1)
    return rolling_std * math.sqrt(periods_per_year)


def cumulative_from_returns(returns: pd.Series) -> pd.Series:
    """Reconstruit une courbe de richesse (base 1) à partir des rendements.

    Utile pour calculer un drawdown sur une série de rendements plutôt que sur
    des prix, conformément à la convention de `METHODOLOGY.md` §8.
    """
    return (1.0 + returns.fillna(0.0)).cumprod()


def drawdown_series(wealth: pd.Series) -> pd.Series:
    """Drawdown relatif : `valeur / plus haut historique - 1` (toujours <= 0)."""
    numeric = _check_prices(wealth, name="wealth")
    running_peak = numeric.cummax()
    return numeric / running_peak - 1.0


def max_drawdown(wealth: pd.Series) -> dict[str, Any]:
    """Drawdown maximal, avec dates du sommet et du creux.

    Convention : la courbe analysée peut être un indice base 100 ou une richesse
    reconstituée ; le résultat est identique puisque le drawdown est relatif.
    """
    drawdown = drawdown_series(wealth)
    if drawdown.empty:
        raise ValueError("Série vide : drawdown indéfini.")
    trough_date = drawdown.idxmin()
    peak_value = wealth.loc[:trough_date].max()
    peak_date = wealth.loc[:trough_date].idxmax()
    return {
        "max_drawdown": float(drawdown.min()),
        "trough_date": pd.Timestamp(trough_date),
        "peak_date": pd.Timestamp(peak_date),
        "peak_value": float(peak_value),
        "trough_value": float(wealth.loc[trough_date]),
    }


def describe_returns(returns: pd.Series, *, percent: bool = True) -> dict[str, float]:
    """Statistiques descriptives d'une série de rendements (METHODOLOGY §6)."""
    numeric = pd.to_numeric(returns, errors="coerce").astype("float64").dropna()
    if numeric.empty:
        raise ValueError("Série de rendements vide : aucune statistique disponible.")
    scale = 100.0 if percent else 1.0
    return {
        "observations": int(numeric.size),
        "mean": float(numeric.mean()) * scale,
        "median": float(numeric.median()) * scale,
        "std": float(numeric.std(ddof=1)) * scale,
        "min": float(numeric.min()) * scale,
        "q05": float(numeric.quantile(0.05)) * scale,
        "q25": float(numeric.quantile(0.25)) * scale,
        "q75": float(numeric.quantile(0.75)) * scale,
        "q95": float(numeric.quantile(0.95)) * scale,
        "max": float(numeric.max()) * scale,
        "skew": float(numeric.skew()),
        "positive_share": float((numeric > 0).mean()) * scale,
        "unit": "%" if percent else "decimal",
    }


def describe_returns_table(returns: pd.DataFrame, *, percent: bool = True) -> pd.DataFrame:
    """Applique `describe_returns` à chaque colonne d'un panel de rendements."""
    return pd.DataFrame(
        {column: describe_returns(returns[column], percent=percent) for column in returns.columns}
    ).T


def pairwise_observations(a: pd.Series, b: pd.Series) -> int:
    """Nombre d'observations appariées valides pour deux séries de rendements."""
    aligned = pd.concat(
        [pd.to_numeric(a, errors="coerce"), pd.to_numeric(b, errors="coerce")], axis=1, join="inner"
    ).dropna()
    return int(len(aligned))


def correlation_matrix(returns: pd.DataFrame, *, method: str = "pearson") -> pd.DataFrame:
    """Matrice de corrélation des rendements alignés (BR-012).

    Chaque paire n'utilise que ses observations communes ; le nombre
    d'observations appariées est disponible via `pairwise_observations`.
    """
    numeric = returns.apply(pd.to_numeric, errors="coerce")
    if numeric.shape[1] < 2:
        raise ValueError("Au moins deux séries de rendements sont nécessaires.")
    matrix = numeric.corr(method=method)
    return matrix


def constant_series_warning(values: pd.Series) -> bool:
    """Indique si une série est constante (corrélation indéfinie)."""
    numeric = pd.to_numeric(values, errors="coerce").dropna()
    return bool(numeric.nunique() <= 1)


def normalized_indices(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Normalise chaque colonne d'un panel de prix en base 100 (BR-004)."""
    indices: dict[str, pd.Series] = {}
    bases: dict[str, dict[str, Any]] = {}
    for column in panel.columns:
        index, base_value, base_date = normalize_base_100(panel[column], name=str(column))
        indices[column] = index
        bases[column] = {
            "base_date": base_date.date().isoformat(),
            "base_value": base_value,
            "base_index": 100.0,
        }
    return pd.DataFrame(indices, index=panel.index), bases
