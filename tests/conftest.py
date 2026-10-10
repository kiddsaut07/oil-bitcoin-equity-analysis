"""Fixtures synthétiques déterministes pour les tests unitaires.

Ces données sont **fictives** : elles servent uniquement à tester des
formules. Elles ne doivent jamais être présentées comme des observations
historiques (BR-020).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def make_series(values: list[float], start: str = "2020-01-01", freq: str = "D") -> pd.Series:
    """Construit une `pd.Series` de prix datée, utile pour les tests de métriques."""
    index = pd.date_range(start=start, periods=len(values), freq=freq)
    return pd.Series(values, index=index, dtype="float64", name="close")


def make_frame(values: list[float], start: str = "2020-01-01", freq: str = "D") -> pd.DataFrame:
    """Construit un DataFrame (`date`, `close`) synthétique."""
    index = pd.date_range(start=start, periods=len(values), freq=freq)
    return pd.DataFrame({"date": index, "close": [float(value) for value in values]})


@pytest.fixture
def simple_prices() -> pd.Series:
    """Série de prix croissante et parfaitement connue : [10, 20, 15]."""
    return make_series([10.0, 20.0, 15.0])


@pytest.fixture
def two_observations() -> pd.Series:
    """Deux prix consécutifs : [100, 110]."""
    return make_series([100.0, 110.0])


@pytest.fixture
def frame_with_duplicates() -> pd.DataFrame:
    """Cadre contenant une date dupliquée, un NaN et un écart de calendrier."""
    return pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2020-01-03", "2020-01-01", "2020-01-02", "2020-01-02", "2020-01-10"]
            ),
            "close": [30.0, 10.0, 20.0, 21.0, np.nan],
        }
    )


@pytest.fixture
def frame_with_missing_tokens() -> pd.DataFrame:
    """Cadre utilisant les marqueurs de valeur manquante de l'export FRED."""
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"]),
            "close": ["61.17", ".", ""],
        }
    )


@pytest.fixture
def two_aligned_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Deux séries avec un jour ouvré commun manquant chez l'une des deux."""
    left = make_frame([10.0, 20.0, 30.0, 40.0], start="2020-01-01")
    right = pd.DataFrame(
        {
            "date": pd.to_datetime(["2020-01-01", "2020-01-02", "2020-01-04"]),
            "close": [1.0, 2.0, 4.0],
        }
    )
    return left, right


@pytest.fixture
def drawdown_case() -> pd.Series:
    """Série dont le sommet est 100 puis 80 : drawdown attendu de -20 %."""
    return make_series([100.0, 80.0, 120.0], start="2020-01-01")
