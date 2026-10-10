"""Tests unitaires des métriques : base 100, rendements, volatilité, drawdown, corrélation.

Toutes les valeurs attendues sont calculables à la main : ce sont des tests
numériques, pas des tests de non-régression opaques.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from src import metrics
from tests.conftest import make_series


class TestBase100:
    def test_known_example(self, simple_prices) -> None:
        index, base_value, base_date = metrics.normalize_base_100(simple_prices)
        assert base_value == 10.0
        assert base_date == pd.Timestamp("2020-01-01")
        np.testing.assert_allclose(index.values, [100.0, 200.0, 150.0])

    def test_normalised_panel_reports_bases(self) -> None:
        panel = pd.DataFrame(
            {"WTI": [10.0, 12.0], "BTC_USD": [100.0, 50.0]},
            index=pd.to_datetime(["2020-01-01", "2020-01-02"]),
        )
        indices, bases = metrics.normalized_indices(panel)
        assert bases["WTI"] == {
            "base_date": "2020-01-01",
            "base_value": 10.0,
            "base_index": 100.0,
        }
        np.testing.assert_allclose(indices["BTC_USD"].values, [100.0, 50.0])

    def test_non_positive_base_raises(self) -> None:
        series = make_series([0.0, 5.0])
        with pytest.raises(ValueError, match="non positif"):
            metrics.normalize_base_100(series)

    def test_nan_price_raises(self) -> None:
        series = make_series([10.0, np.nan])
        with pytest.raises(ValueError, match="non finis"):
            metrics.normalize_base_100(series)

    def test_empty_series_raises(self) -> None:
        with pytest.raises(ValueError, match="vide"):
            metrics.normalize_base_100(make_series([]))


class TestSimpleReturns:
    def test_known_example(self, two_observations) -> None:
        returns = metrics.simple_returns(two_observations)
        assert math.isnan(returns.iloc[0])
        assert returns.iloc[1] == pytest.approx(0.10)

    def test_downward_move(self, simple_prices) -> None:
        returns = metrics.simple_returns(simple_prices)
        assert returns.iloc[1] == pytest.approx(1.0)
        assert returns.iloc[2] == pytest.approx(-0.25)

    def test_gap_beyond_threshold_is_excluded(self) -> None:
        prices = pd.Series(
            [100.0, 110.0],
            index=pd.to_datetime(["2020-01-01", "2020-01-20"]),
        )
        returns = metrics.simple_returns(prices, max_gap_days=7.0)
        assert math.isnan(returns.iloc[1])

    def test_non_positive_previous_price_is_excluded(self) -> None:
        prices = pd.Series([0.0, 10.0], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
        returns = metrics.simple_returns(prices)
        assert math.isnan(returns.iloc[1])

    def test_gap_control_can_be_disabled(self) -> None:
        prices = pd.Series([100.0, 110.0], index=pd.to_datetime(["2020-01-01", "2020-01-20"]))
        assert metrics.simple_returns(prices, max_gap_days=None).iloc[1] == pytest.approx(0.10)


class TestLogReturns:
    def test_known_example(self, two_observations) -> None:
        returns = metrics.log_returns(two_observations)
        assert returns.iloc[1] == pytest.approx(math.log(1.1))

    def test_non_positive_price_yields_nan_and_warning(self) -> None:
        prices = pd.Series([0.0, 10.0], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
        with pytest.warns(RuntimeWarning, match="non définis"):
            returns = metrics.log_returns(prices)
        assert math.isnan(returns.iloc[1])

    def test_non_positive_price_can_raise(self) -> None:
        prices = pd.Series([0.0, 10.0], index=pd.to_datetime(["2020-01-01", "2020-01-02"]))
        with pytest.raises(ValueError, match="indéfinis"):
            metrics.log_returns(prices, on_invalid="raise")


class TestVolatility:
    def test_annualisation_formula(self) -> None:
        returns = make_series([0.01, -0.01, 0.02, -0.02])
        expected = metrics.sample_std(returns) * math.sqrt(252)
        assert metrics.annualized_volatility(returns) == pytest.approx(expected)

    def test_convention_365_differs_from_252(self) -> None:
        returns = make_series([0.01, -0.01, 0.02, -0.02])
        assert metrics.annualized_volatility(returns, periods_per_year=365) > (
            metrics.annualized_volatility(returns, periods_per_year=252)
        )

    def test_single_observation_raises(self) -> None:
        with pytest.raises(ValueError, match="au moins deux"):
            metrics.sample_std(make_series([0.01]))

    def test_constant_returns_have_zero_volatility(self) -> None:
        returns = make_series([0.01, 0.01, 0.01])
        assert metrics.annualized_volatility(returns) == pytest.approx(0.0)

    def test_rolling_window_needs_minimum(self) -> None:
        with pytest.raises(ValueError, match="au moins deux"):
            metrics.rolling_volatility(make_series([0.01, 0.02]), window=1)

    def test_rolling_values_start_after_window(self) -> None:
        returns = make_series([0.01, -0.01, 0.02, -0.02, 0.01])
        rolling = metrics.rolling_volatility(returns, window=3)
        assert rolling.iloc[:2].isna().all()
        assert rolling.iloc[2:].notna().all()


class TestDrawdown:
    def test_known_peak_and_trough(self, drawdown_case) -> None:
        result = metrics.max_drawdown(drawdown_case)
        assert result["max_drawdown"] == pytest.approx(-0.20)
        assert result["trough_date"] == pd.Timestamp("2020-01-02")
        assert result["peak_date"] == pd.Timestamp("2020-01-01")

    def test_drawdown_is_never_positive(self) -> None:
        drawdown = metrics.drawdown_series(make_series([100.0, 120.0, 90.0]))
        assert (drawdown <= 0).all()

    def test_monotonic_series_has_zero_drawdown(self) -> None:
        result = metrics.max_drawdown(make_series([100.0, 110.0, 120.0]))
        assert result["max_drawdown"] == pytest.approx(0.0)

    def test_wealth_reconstruction_matches_prices(self) -> None:
        prices = make_series([100.0, 110.0, 99.0])
        returns = metrics.simple_returns(prices)
        wealth = metrics.cumulative_from_returns(returns)
        np.testing.assert_allclose(wealth.values[1:], prices.values[1:] / prices.values[0])


class TestDescription:
    def test_descriptive_statistics_on_known_series(self) -> None:
        returns = make_series([0.0, 0.1, -0.1, 0.2])
        stats = metrics.describe_returns(returns)
        assert stats["observations"] == 4
        assert stats["mean"] == pytest.approx(5.0)
        assert stats["min"] == pytest.approx(-10.0)
        assert stats["max"] == pytest.approx(20.0)
        assert stats["unit"] == "%"

    def test_decimal_unit_option(self) -> None:
        stats = metrics.describe_returns(make_series([0.1]), percent=False)
        assert stats["mean"] == pytest.approx(0.1)
        assert stats["unit"] == "decimal"

    def test_empty_series_raises(self) -> None:
        with pytest.raises(ValueError, match="vide"):
            metrics.describe_returns(pd.Series([np.nan], dtype="float64"))


class TestCorrelation:
    def test_identical_series_correlate_perfectly(self) -> None:
        returns = make_series([0.01, -0.02, 0.03, -0.01, 0.02])
        matrix = metrics.correlation_matrix(pd.DataFrame({"A": returns, "B": returns}))
        assert matrix.loc["A", "B"] == pytest.approx(1.0)
        assert matrix.loc["A", "A"] == pytest.approx(1.0)

    def test_opposite_series_correlate_negatively(self) -> None:
        returns = make_series([0.01, -0.02, 0.03, -0.01, 0.02])
        matrix = metrics.correlation_matrix(pd.DataFrame({"A": returns, "B": -returns}))
        assert matrix.loc["A", "B"] == pytest.approx(-1.0)

    def test_pairwise_observations_count(self) -> None:
        index = pd.date_range("2020-01-01", periods=4, freq="D")
        left = pd.Series([0.1, np.nan, 0.3, 0.4], index=index)
        right = pd.Series([0.2, 0.3, np.nan, 0.5], index=index)
        assert metrics.pairwise_observations(left, right) == 2

    def test_constant_series_is_flagged_and_gives_nan_correlation(self) -> None:
        constant = make_series([0.01, 0.01, 0.01])
        moving = make_series([0.02, -0.01, 0.03])
        assert metrics.constant_series_warning(constant)
        assert not metrics.constant_series_warning(moving)
        matrix = metrics.correlation_matrix(pd.DataFrame({"A": constant, "B": moving}))
        assert math.isnan(matrix.loc["A", "B"])

    def test_correlation_needs_two_series(self) -> None:
        with pytest.raises(ValueError, match="Au moins deux"):
            metrics.correlation_matrix(pd.DataFrame({"A": make_series([0.1, 0.2])}))
