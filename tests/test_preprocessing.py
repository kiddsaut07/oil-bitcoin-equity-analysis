"""Tests unitaires du prétraitement : schéma, dates, doublons, qualité, alignement.

Aucune donnée réelle ni aucun accès réseau : uniquement des fixtures
synthétiques déterministes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import preprocessing
from src.preprocessing import EmptyDataError, SchemaError


class TestSchema:
    def test_missing_column_raises(self) -> None:
        frame = pd.DataFrame({"date": pd.to_datetime(["2020-01-01"]), "value": [1.0]})
        with pytest.raises(SchemaError, match="Colonnes manquantes"):
            preprocessing.validate_schema(frame)

    def test_empty_frame_raises(self) -> None:
        frame = pd.DataFrame({"date": pd.to_datetime([]), "close": []})
        with pytest.raises(EmptyDataError):
            preprocessing.validate_schema(frame)

    def test_valid_frame_passes(self, simple_prices) -> None:
        frame = simple_prices.reset_index().rename(columns={"index": "date"})
        preprocessing.validate_schema(frame)

    def test_missing_tokens_become_nan(self, frame_with_missing_tokens) -> None:
        result = preprocessing.to_numeric_close(frame_with_missing_tokens)
        assert result["close"].iloc[0] == 61.17
        assert result["close"].iloc[1:].isna().all()
        assert result["close"].dtype == np.float64

    def test_unparsable_price_becomes_nan(self) -> None:
        frame = pd.DataFrame({"date": pd.to_datetime(["2020-01-02"]), "close": ["n/a"]})
        assert np.isnan(preprocessing.to_numeric_close(frame)["close"].iloc[0])


class TestDates:
    def test_dates_are_parsed_and_sorted(self, frame_with_duplicates) -> None:
        result = preprocessing.parse_dates(preprocessing.sort_by_date(frame_with_duplicates))
        assert result["date"].is_monotonic_increasing
        assert pd.api.types.is_datetime64_any_dtype(result["date"])

    def test_invalid_date_raises(self) -> None:
        frame = pd.DataFrame({"date": ["2020-01-01", "pas une date"], "close": [1.0, 2.0]})
        with pytest.raises(SchemaError, match="Dates non convertibles"):
            preprocessing.parse_dates(frame)

    def test_coerce_marks_invalid_dates_as_nat(self) -> None:
        frame = pd.DataFrame({"date": ["2020-01-01", "pas une date"], "close": [1.0, 2.0]})
        result = preprocessing.parse_dates(frame, errors="coerce")
        assert result["date"].isna().sum() == 1

    def test_aware_timestamps_are_normalised(self) -> None:
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(["2020-01-02T23:30:00+00:00"]),
                "close": [1.0],
            }
        )
        result = preprocessing.parse_dates(frame)
        assert str(result["date"].iloc[0]) == "2020-01-02 00:00:00"


class TestDuplicates:
    def test_duplicates_are_detected_before_removal(self, frame_with_duplicates) -> None:
        duplicates = preprocessing.find_duplicates(frame_with_duplicates)
        assert duplicates == [pd.Timestamp("2020-01-02")]

    def test_drop_duplicate_dates_keeps_last(self, frame_with_duplicates) -> None:
        result = preprocessing.drop_duplicate_dates(frame_with_duplicates)
        assert len(result) == 4
        january_second = result.loc[result["date"] == pd.Timestamp("2020-01-02"), "close"]
        assert january_second.tolist() == [21.0]

    def test_no_duplicate_is_a_no_op(self, two_aligned_frames) -> None:
        left, _ = two_aligned_frames
        assert len(preprocessing.drop_duplicate_dates(left)) == len(left)


class TestPeriodSelection:
    def test_bounds_are_inclusive(self, two_aligned_frames) -> None:
        left, _ = two_aligned_frames
        result = preprocessing.select_period(left, "2020-01-02", "2020-01-03")
        assert result["date"].tolist() == [
            pd.Timestamp("2020-01-02"),
            pd.Timestamp("2020-01-03"),
        ]

    def test_period_outside_data_returns_empty(self, two_aligned_frames) -> None:
        left, _ = two_aligned_frames
        assert preprocessing.select_period(left, "2021-01-01", "2021-12-31").empty


class TestQualityAudit:
    def test_audit_counts_missing_and_duplicates(self, frame_with_duplicates) -> None:
        report = preprocessing.audit_quality(frame_with_duplicates)
        assert report["rows"] == 5
        assert report["duplicate_dates"] == 1
        assert report["missing_close"] == 1
        assert report["first_date"] == "2020-01-01"
        assert report["last_date"] == "2020-01-10"
        assert report["observed_gap_days_max"] == 7.0

    def test_audit_flags_non_positive_prices(self) -> None:
        frame = pd.DataFrame(
            {"date": pd.to_datetime(["2020-01-01", "2020-01-02"]), "close": [10.0, -5.0]}
        )
        report = preprocessing.audit_quality(frame)
        assert report["non_positive"] == 1

    def test_audit_counts_extreme_moves(self) -> None:
        frame = pd.DataFrame(
            {"date": pd.to_datetime(["2020-01-01", "2020-01-02"]), "close": [10.0, 30.0]}
        )
        report = preprocessing.audit_quality(frame)
        assert report["moves_over_threshold"] == 1
        assert report["largest_move"] == pytest.approx(2.0)


class TestAlignment:
    def test_alignment_keeps_only_common_dates(self, two_aligned_frames) -> None:
        left, right = two_aligned_frames
        panel = preprocessing.align_common_dates({"A": left, "B": right})
        assert panel.index.tolist() == [
            pd.Timestamp("2020-01-01"),
            pd.Timestamp("2020-01-02"),
            pd.Timestamp("2020-01-04"),
        ]
        assert not panel.isna().any().any()

    def test_alignment_report_documents_losses(self, two_aligned_frames) -> None:
        left, right = two_aligned_frames
        panel = preprocessing.align_common_dates({"A": left, "B": right})
        report = preprocessing.alignment_report({"A": left, "B": right}, panel)
        assert report["observations_before"] == {"A": 4, "B": 3}
        assert report["observations_aligned"] == 3
        assert report["observations_lost"] == {"A": 1, "B": 0}

    def test_empty_intersection_raises(self) -> None:
        left = pd.DataFrame({"date": pd.to_datetime(["2020-01-01"]), "close": [1.0]})
        right = pd.DataFrame({"date": pd.to_datetime(["2021-01-01"]), "close": [1.0]})
        with pytest.raises(EmptyDataError, match="Aucune date commune"):
            preprocessing.align_common_dates({"A": left, "B": right})

    def test_alignment_refuses_duplicates(self, frame_with_duplicates) -> None:
        with pytest.raises(SchemaError, match="Doublons"):
            preprocessing.align_common_dates({"A": frame_with_duplicates})

    def test_align_requires_at_least_one_frame(self) -> None:
        with pytest.raises(SchemaError, match="Aucun cadre"):
            preprocessing.align_common_dates({})


class TestWeeklyResampling:
    def test_last_observation_of_each_week_is_kept(self) -> None:
        dates = pd.to_datetime(
            ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-10"]
        )
        data = pd.DataFrame({"date": dates, "close": [1.0, 2.0, 3.0, 4.0, 5.0]})
        weekly = preprocessing.resample_weekly(data)
        assert len(weekly) == 2
        assert weekly["close"].tolist() == [2.0, 5.0]
        assert weekly.index[0] == pd.Timestamp("2020-01-05")


class TestLongFormat:
    def test_pivot_long_restores_asset_column(self, two_aligned_frames) -> None:
        left, right = two_aligned_frames
        panel = preprocessing.align_common_dates({"A": left, "B": right})
        long = preprocessing.pivot_long(panel)
        assert set(long.columns) == {"date", "asset", "close"}
        assert len(long) == 6


class TestPositiveAssertion:
    def test_non_positive_price_raises(self) -> None:
        series = pd.Series([1.0, 0.0], index=pd.date_range("2020-01-01", periods=2))
        with pytest.raises(SchemaError, match="non finis ou non positifs"):
            preprocessing.assert_positive(series)

    def test_nan_price_raises(self) -> None:
        series = pd.Series([1.0, np.nan], index=pd.date_range("2020-01-01", periods=2))
        with pytest.raises(SchemaError):
            preprocessing.assert_positive(series)

    def test_positive_series_passes(self) -> None:
        series = pd.Series([1.0, 2.0], index=pd.date_range("2020-01-01", periods=2))
        preprocessing.assert_positive(series)
