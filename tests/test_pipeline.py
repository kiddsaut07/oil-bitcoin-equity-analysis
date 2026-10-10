"""Tests d'orchestration du pipeline en mode hors ligne (`--offline`).

Le mode hors ligne relit des copies locales synthétiques de `data/raw/`, ce qui
permet de tester toute la chaîne — acquisition écartée, qualité, alignement,
calculs, écriture des artefacts — sans dépendre du réseau (BR-015, BR-020).
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from src import pipeline, preprocessing


def _write_raw(raw_dir, asset: str, frame: pd.DataFrame) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(raw_dir / f"{asset}.csv", index=False)
    (raw_dir / f"{asset}_metadata.json").write_text(
        json.dumps(
            {
                "asset": asset,
                "provider": "source de test",
                "series_id": asset,
                "unit": "unitaire",
                "currency": "USD",
                "retrieved_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def offline_raw(tmp_path):
    """Trois séries synthétiques partageant quatre dates communes."""
    raw_dir = tmp_path / "raw"
    dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"])
    _write_raw(raw_dir, "WTI", pd.DataFrame({"date": dates, "close": [60.0, 61.0, 55.0, 58.0]}))
    _write_raw(
        raw_dir,
        "SP500",
        pd.DataFrame({"date": dates, "close": [3200.0, 3250.0, 3100.0, 3300.0]}),
    )
    _write_raw(
        raw_dir,
        "BTC_USD",
        pd.DataFrame({"date": dates, "close": [7200.0, 7400.0, 7000.0, 8000.0]}),
    )
    return raw_dir


class TestOfflinePipeline:
    def test_pipeline_aligns_and_computes_every_step(self, offline_raw, tmp_path) -> None:
        processed = tmp_path / "processed"
        result = pipeline.run_pipeline(
            "2020-01-01", "2020-12-31", raw_dir=offline_raw, processed_dir=processed, offline=True
        )
        assert result.prices.shape == (4, 3)
        assert list(result.prices.columns) == ["WTI", "BTC_USD", "SP500"]
        assert result.indices.iloc[0].tolist() == [100.0, 100.0, 100.0]
        assert result.returns["WTI"].iloc[1] == pytest.approx(1.0 / 60.0)
        assert result.drawdowns["WTI"].min() == pytest.approx(55.0 / 61.0 - 1.0)
        assert result.alignment["observations_aligned"] == 4

    def test_artifacts_are_written_with_metadata(self, offline_raw, tmp_path) -> None:
        processed = tmp_path / "processed"
        pipeline.run_pipeline(
            "2020-01-01", "2020-12-31", raw_dir=offline_raw, processed_dir=processed, offline=True
        )
        for name in (
            "prices_aligned.csv",
            "indices_base100.csv",
            "returns_simple.csv",
            "returns_log.csv",
            "drawdowns.csv",
            "quality_report.json",
        ):
            assert (processed / name).exists()
        report = json.loads((processed / "quality_report.json").read_text(encoding="utf-8"))
        assert report["periods_per_year"] == 252
        assert set(report["quality"]) == {"WTI", "BTC_USD", "SP500"}
        assert report["alignment"]["observations_aligned"] == 4

    def test_quality_report_documents_missing_values(self, tmp_path) -> None:
        raw_dir = tmp_path / "raw"
        dates = pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06"])
        _write_raw(raw_dir, "WTI", pd.DataFrame({"date": dates, "close": [1.0, np.nan, 3.0]}))
        _write_raw(raw_dir, "SP500", pd.DataFrame({"date": dates, "close": [1.0, 2.0, 3.0]}))
        _write_raw(raw_dir, "BTC_USD", pd.DataFrame({"date": dates, "close": [1.0, 2.0, 3.0]}))
        result = pipeline.run_pipeline(
            "2020-01-01", "2020-12-31", raw_dir=raw_dir, processed_dir=tmp_path / "p", offline=True
        )
        assert result.quality["WTI"]["missing_close"] == 1
        assert result.prices.shape[0] == 2

    def test_period_filter_is_inclusive(self, offline_raw, tmp_path) -> None:
        result = pipeline.run_pipeline(
            "2020-01-03",
            "2020-01-06",
            raw_dir=offline_raw,
            processed_dir=tmp_path / "p",
            offline=True,
        )
        assert result.alignment["first_aligned_date"] == "2020-01-03"
        assert result.alignment["last_aligned_date"] == "2020-01-06"
        assert len(result.prices) == 2

    def test_missing_local_copy_raises_actionable_error(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="Relancer une fois sans --offline"):
            pipeline.run_pipeline(
                "2020-01-01",
                "2020-12-31",
                assets=("WTI",),
                raw_dir=tmp_path / "empty",
                processed_dir=tmp_path / "p",
                offline=True,
            )

    def test_inverted_period_raises(self, offline_raw, tmp_path) -> None:
        with pytest.raises(ValueError, match="Période invalide"):
            pipeline.run_pipeline(
                "2021-01-01",
                "2020-01-01",
                raw_dir=offline_raw,
                processed_dir=tmp_path / "p",
                offline=True,
            )

    def test_unsorted_duplicate_raw_input_is_cleaned(self, tmp_path) -> None:
        raw_dir = tmp_path / "raw"
        dates = pd.to_datetime(["2020-01-03", "2020-01-02", "2020-01-02"])
        _write_raw(raw_dir, "WTI", pd.DataFrame({"date": dates, "close": [2.0, 1.0, 1.5]}))
        _write_raw(raw_dir, "SP500", pd.DataFrame({"date": dates[:2], "close": [2.0, 1.0]}))
        _write_raw(raw_dir, "BTC_USD", pd.DataFrame({"date": dates[:2], "close": [2.0, 1.0]}))
        result = pipeline.run_pipeline(
            "2020-01-01", "2020-12-31", raw_dir=raw_dir, processed_dir=tmp_path / "p", offline=True
        )
        assert result.prices.index.is_monotonic_increasing
        assert result.quality["WTI"]["duplicate_dates"] == 1
        assert result.prices["WTI"].iloc[0] == 1.5


class TestWeeklySensitivity:
    def test_weekly_series_supports_metrics(self, offline_raw) -> None:
        raw = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07", "2020-01-13"]
                ),
                "close": [10.0, 12.0, 11.0, 14.0, 13.0],
            }
        )
        weekly = preprocessing.resample_weekly(raw)
        assert weekly["close"].tolist() == [12.0, 14.0, 13.0]
        assert weekly.index.is_monotonic_increasing
