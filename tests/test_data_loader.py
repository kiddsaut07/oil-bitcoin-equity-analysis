"""Tests unitaires de la récupération des données — aucun accès réseau.

Un transport factice (`transports=[...]`) remplace l'accès Internet : on peut
ainsi vérifier le parsing, le découpage des requêtes et surtout la gestion
d'erreur exigée par BR-015 (aucune donnée fictive en cas d'échec).
"""

from __future__ import annotations

import urllib.error

import pandas as pd
import pytest

from src import data_loader
from src.data_loader import DataSourceError, TransportError

FRED_CSV = b"observation_date,SP500\n2020-01-02,3257.85\n2020-01-03,3234.85\n2020-01-06,.\n"
COINBASE_JSON = b"[[1577923200,1,2,1,1.5,10],[1578009600,1,2,1,2.5,10]]"


class FakeTransport:
    """Transport factice qui renvoie desoctets préparés et journalise les URLs."""

    def __init__(self, payloads: bytes | list[bytes] | Exception) -> None:
        if isinstance(payloads, (bytes, Exception)):
            payloads = [payloads]
        self.payloads = list(payloads)
        self.calls: list[str] = []

    def __call__(self, url: str, *, timeout: int = 60) -> bytes:
        self.calls.append(url)
        index = min(len(self.calls) - 1, len(self.payloads) - 1)
        payload = self.payloads[index]
        if isinstance(payload, Exception):
            raise payload
        return payload


class TestSeriesRegistry:
    def test_known_series_are_declared(self) -> None:
        assert set(data_loader.SERIES) == {"WTI", "BTC_USD", "SP500"}

    def test_series_descriptions_carry_unit_and_licence(self) -> None:
        description = data_loader.describe_series("WTI")
        assert description["unit"] == "USD par baril"
        assert "Energy Information Administration" in description["provider"]
        assert description["terms_note"]

    def test_sp500_is_declared_as_price_index(self) -> None:
        assert "dividendes" in data_loader.describe_series("SP500")["price_definition"].lower()

    def test_unknown_series_raises(self) -> None:
        with pytest.raises(DataSourceError, match="Série inconnue"):
            data_loader.fetch_series("PETROL", "2020-01-01", "2020-01-02")


class TestFredParsing:
    def test_csv_is_parsed_into_date_and_close(self) -> None:
        frame = data_loader.parse_fred_csv(FRED_CSV, data_loader.SERIES["SP500"])
        assert frame["date"].tolist() == [
            pd.Timestamp("2020-01-02"),
            pd.Timestamp("2020-01-03"),
            pd.Timestamp("2020-01-06"),
        ]
        assert frame["close"].iloc[0] == 3257.85

    def test_missing_marker_becomes_nan(self) -> None:
        frame = data_loader.parse_fred_csv(FRED_CSV, data_loader.SERIES["SP500"])
        assert pd.isna(frame["close"].iloc[2])

    def test_empty_payload_raises(self) -> None:
        with pytest.raises(DataSourceError, match="vide"):
            data_loader.parse_fred_csv(b"", data_loader.SERIES["SP500"])

    def test_unexpected_columns_raise(self) -> None:
        with pytest.raises(DataSourceError, match="Colonnes inattendues"):
            data_loader.parse_fred_csv(b"foo,bar\n1,2\n", data_loader.SERIES["SP500"])

    def test_fetch_builds_expected_url_and_metadata(self) -> None:
        transport = FakeTransport(FRED_CSV)
        frame, metadata = data_loader.fetch_fred_series(
            data_loader.SERIES["SP500"], "2020-01-01", "2020-01-10", transports=[transport]
        )
        assert "id=SP500" in transport.calls[0]
        assert "cosd=2020-01-01" in transport.calls[0] and "coed=2020-01-10" in transport.calls[0]
        assert metadata["series_id"] == "SP500"
        assert metadata["rows_returned"] == len(frame) == 3
        assert metadata["first_observation"] == "2020-01-02"
        assert metadata["retrieved_at"].endswith("+00:00")
        assert "api_key" not in str(metadata).lower()


class TestCoinbaseParsing:
    def test_candles_use_the_close_field(self) -> None:
        frame = data_loader.parse_coinbase_candles(COINBASE_JSON, data_loader.SERIES["BTC_USD"])
        assert frame["close"].tolist() == [1.5, 2.5]
        assert frame["date"].iloc[0] == pd.Timestamp("2020-01-02")

    def test_error_payload_raises(self) -> None:
        with pytest.raises(DataSourceError, match="Réponse inattendue"):
            data_loader.parse_coinbase_candles(
                b'{"message": "invalid"}', data_loader.SERIES["BTC_USD"]
            )

    def test_empty_candles_raise(self) -> None:
        with pytest.raises(DataSourceError, match="Aucune bougie"):
            data_loader.parse_coinbase_candles(b"[]", data_loader.SERIES["BTC_USD"])

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(DataSourceError, match="illisible"):
            data_loader.parse_coinbase_candles(b"not json", data_loader.SERIES["BTC_USD"])

    def test_long_period_is_split_into_chunks(self) -> None:
        payload = b"[[1577923200,1,2,1,7.0,10]]"
        transport = FakeTransport(payload)
        frame, metadata = data_loader.fetch_coinbase_daily_candles(
            data_loader.SERIES["BTC_USD"],
            "2020-01-01",
            "2022-12-31",
            transports=[transport],
            sleep=lambda _: None,
            pause=0.0,
            chunk_days=290,
        )
        assert len(transport.calls) == 4
        assert all("granularity=86400" in url for url in transport.calls)
        assert len(frame) == 1
        assert metadata["http_requests"] == 4

    def test_period_filter_removes_out_of_window_candles(self) -> None:
        transport = FakeTransport(COINBASE_JSON)
        frame, _ = data_loader.fetch_coinbase_daily_candles(
            data_loader.SERIES["BTC_USD"],
            "2020-01-03",
            "2020-01-05",
            transports=[transport],
            sleep=lambda _: None,
            pause=0.0,
        )
        assert frame["date"].tolist() == [pd.Timestamp("2020-01-03")]


class TestFailureHandling:
    def test_http_404_raises_data_source_error(self) -> None:
        transport = FakeTransport(TransportError("statut HTTP 404", status=404))
        with pytest.raises(DataSourceError, match="Erreur HTTP 404"):
            data_loader.http_get_bytes(
                "https://example.invalid/x", transports=[transport], sleep=lambda _: None
            )

    def test_transient_failure_is_retried_then_succeeds(self) -> None:
        class FlakyTransport:
            def __init__(self) -> None:
                self.calls = 0

            def __call__(self, url: str, *, timeout: int = 60) -> bytes:
                self.calls += 1
                if self.calls < 3:
                    raise TransportError("délai dépassé (60s)")
                return b"ok"

        transport = FlakyTransport()
        delays: list[float] = []
        result = data_loader.http_get_bytes(
            "https://example.invalid/x",
            transports=[transport],
            sleep=delays.append,
            retries=5,
            backoff=2.0,
        )
        assert result == b"ok"
        assert transport.calls == 3
        assert delays == [2.0, 4.0]

    def test_network_failure_never_returns_fabricated_data(self) -> None:
        transport = FakeTransport(TransportError("réseau injoignable"))
        with pytest.raises(DataSourceError) as error:
            data_loader.http_get_bytes(
                "https://example.invalid/x",
                transports=[transport],
                sleep=lambda _: None,
                retries=2,
            )
        assert "Aucune donnée fictive" in str(error.value)
        assert len(transport.calls) == 2

    def test_fetch_series_propagates_error(self) -> None:
        transport = FakeTransport(TransportError("réseau injoignable"))
        with pytest.raises(DataSourceError):
            data_loader.fetch_series(
                "SP500", "2020-01-01", "2020-01-10", transports=[transport], sleep=lambda _: None
            )

    def test_urllib_transport_wraps_http_errors(self) -> None:
        def failing_opener(request, timeout=None):
            raise urllib.error.HTTPError(request.full_url, 503, "Service Unavailable", {}, None)

        original = data_loader.urllib.request.urlopen
        data_loader.urllib.request.urlopen = failing_opener
        try:
            with pytest.raises(TransportError) as error:
                data_loader.urllib_transport("https://example.invalid/x", timeout=1)
            assert error.value.status == 503
        finally:
            data_loader.urllib.request.urlopen = original
