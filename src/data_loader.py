"""Récupération des séries brutes auprès des fournisseurs documentés.

Ce module ne contient que de l'acquisition et de la normalisation de format.
Il ne fait aucun calcul statistique : il transforme une réponse HTTP en
`pandas.DataFrame` tabulaire (`date`, `close`) et en métadonnées de collecte.

Principes appliqués (voir `BUSINESS_RULES.md`) :

* BR-015 : un échec réseau produit une exception `DataSourceError` explicite.
  Aucune donnée synthétique ne peut se substituer silencieusement à une donnée
  réelle.
* BR-016 : chaque réponse est accompagnée de métadonnées (fournisseur,
  identifiant, URL, paramètres, horodatage de collecte).
* BR-002 : unité, devise, fréquence et convention de clôture sont décrites
  dans le registre `SERIES` et reportées dans les métadonnées.

Fournisseurs retenus (vérifiés depuis cet environnement, voir `DATA_SOURCES.md`) :

* FRED (Federal Reserve Bank of St. Louis) via l'export CSV
  `https://fred.stlouisfed.org/graph/fredgraph.csv`, sans clé API, pour
  `DCOILWTICO` (WTI spot, source EIA) et `SP500`.
* Coinbase Exchange `GET /products/{product_id}/candles` pour `BTC-USD`,
  sans authentification, 300 bougies maximum par requête.
"""

from __future__ import annotations

import csv
import io
import json
import os
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

FRED_CSV_ENDPOINT = "https://fred.stlouisfed.org/graph/fredgraph.csv"
FRED_SERIES_PAGE = "https://fred.stlouisfed.org/series/{series_id}"
COINBASE_CANDLES_ENDPOINT = "https://api.exchange.coinbase.com/products/{product_id}/candles"
COINBASE_DOC_URL = (
    "https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles"
)

# Le CDN qui sert fred.stlouisfed.org réinitialise la connexion (curl 92) dès
# qu'un User-Agent personnalisé est envoyé : mesuré à 0 succès sur 13 essais
# avec `-A ...` contre 8 succès sur 8 avec l'agent par défaut de curl.
# Aucun agent n'est donc envoyé par défaut ; `OBAE_USER_AGENT` permet d'en
# imposer un sur un réseau qui l'exigerait (voir ADR/ADR-003-http-transport.md).
COINBASE_MAX_CANDLES = 300
COINBASE_CHUNK_DAYS = 290
ONE_DAY = timedelta(days=1)

DEFAULT_TIMEOUT = 60
DEFAULT_RETRIES = 5
DEFAULT_BACKOFF = 1.5
URLLIB_TIMEOUT = 30
USER_AGENT = os.environ.get("OBAE_USER_AGENT")

Transport = Callable[..., bytes]


class DataSourceError(RuntimeError):
    """Erreur de récupération : réseau, HTTP ou format de réponse inattendu."""


@dataclass(frozen=True)
class SeriesSpec:
    """Contrat documentaire d'une série : identité, unité, convention, licence."""

    asset: str
    label: str
    provider: str
    series_id: str
    unit: str
    currency: str
    frequency: str
    close_convention: str
    source_url: str
    terms_note: str
    price_definition: str


SERIES: dict[str, SeriesSpec] = {
    "WTI": SeriesSpec(
        asset="WTI",
        label="WTI Crude Oil (spot, Cushing, Oklahoma)",
        provider="FRED (U.S. Energy Information Administration)",
        series_id="DCOILWTICO",
        unit="USD par baril",
        currency="USD",
        frequency="journalière (jours ouvrés US)",
        close_convention="cours spot quotidien, heure de clôture non publiée par la source",
        source_url=FRED_SERIES_PAGE.format(series_id="DCOILWTICO"),
        terms_note=(
            "Export CSV public de FRED, sans clé. Conditions d'utilisation de FRED "
            "non vérifiées depuis cet environnement : à lire sur "
            "https://fred.stlouisfed.org/legal/ avant toute rediffusion."
        ),
        price_definition="Prix spot du WTI, pas un contrat à terme.",
    ),
    "BTC_USD": SeriesSpec(
        asset="BTC_USD",
        label="Bitcoin en dollars américains (Coinbase Exchange)",
        provider="Coinbase Exchange (public market data API)",
        series_id="BTC-USD",
        unit="USD par BTC",
        currency="USD",
        frequency="journalière (7j/7)",
        close_convention=(
            "bougie quotidienne UTC (granularité 86400 s), prix de clôture = dernier "
            "échange de la journée UTC"
        ),
        source_url=COINBASE_DOC_URL,
        terms_note=(
            "Endpoint public sans authentification. Conditions d'utilisation Coinbase "
            "non vérifiées depuis cet environnement : à lire sur "
            "https://www.coinbase.com/legal/user-agreement/ avant toute rediffusion."
        ),
        price_definition="Cours de clôture quotidien d'une seule plateforme, non un indice agrégé.",
    ),
    "SP500": SeriesSpec(
        asset="SP500",
        label="S&P 500 (indice de prix)",
        provider="FRED (S&P Dow Jones Indices, LLC)",
        series_id="SP500",
        unit="points d'indice",
        currency="n/a (indice)",
        frequency="journalière (jours ouvrés US)",
        close_convention="clôture officielle du marché, heure non publiée par la source",
        source_url=FRED_SERIES_PAGE.format(series_id="SP500"),
        terms_note=(
            "Export CSV public de FRED, sans clé. Conditions d'utilisation de FRED "
            "non vérifiées depuis cet environnement : à lire sur "
            "https://fred.stlouisfed.org/legal/ avant toute rediffusion."
        ),
        price_definition="Indice de prix : les dividendes ne sont PAS inclus (BR-018).",
    ),
}

MISSING_MARKERS = {"", ".", "nan", "NaN", "NA", "N/A", "null", "None"}


def describe_series(asset: str) -> dict[str, str]:
    """Retourne le contrat documentaire d'une série sous forme de dictionnaire."""
    return asdict(SERIES[asset])


def _retry_delay(attempt: int, backoff: float, retry_after: str | None = None) -> float:
    """Retourne le délai avant la tentative suivante (exposant, borné)."""
    if retry_after:
        try:
            return max(0.0, float(retry_after))
        except ValueError:
            pass
    return min(backoff**attempt, 60.0)


class TransportError(RuntimeError):
    """Échec d'une tentative de transport HTTP, avec un statut éventuellement connu."""

    def __init__(self, message: str, *, status: int | None = None, retry_after: str | None = None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def _curl_transport(url: str, *, timeout: int, http1: bool) -> bytes:
    """Exécute une requête GET via `curl` et renvoie le corps de la réponse."""
    with tempfile.TemporaryDirectory() as workspace:
        body_path = Path(workspace) / "body"
        header_path = Path(workspace) / "headers"
        command = [
            "curl",
            "--silent",
            "--show-error",
            "--location",
            "--max-time",
            str(timeout),
            *(["--http1.1"] if http1 else []),
            *(["--user-agent", USER_AGENT] if USER_AGENT else []),
            "--dump-header",
            str(header_path),
            "--output",
            str(body_path),
            "--write-out",
            "%{http_code}",
            url,
        ]
        try:
            completed = subprocess.run(
                command, capture_output=True, check=False, timeout=timeout + 15
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise TransportError(f"curl indisponible : {exc}") from exc
        body = body_path.read_bytes() if body_path.exists() else None
        headers_text = (
            header_path.read_text(encoding="utf-8", errors="ignore") if header_path.exists() else ""
        )
    if completed.returncode != 0 and body is None:
        stderr_text = completed.stderr.decode()[:200]
        raise TransportError(f"curl a échoué (code {completed.returncode}) : {stderr_text}")
    status_text = completed.stdout.decode().strip()
    status = int(status_text) if status_text.isdigit() else None
    retry_after = None
    for line in headers_text.splitlines():
        if line.lower().startswith("retry-after:"):
            retry_after = line.split(":", 1)[1].strip()
    if status is not None and status >= 400:
        raise TransportError(f"statut HTTP {status}", status=status, retry_after=retry_after)
    if body is None:
        raise TransportError("réponse HTTP vide")
    return body


def curl_transport(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    """Transport HTTP basé sur l'exécutable `curl` (négociation HTTP/2 par défaut).

    Pourquoi ce transport ? Depuis l'environnement de développement, le CDN
    qui sert `fred.stlouisfed.org` n'achève la négociation TLS/ALPN qu'avec un
    client proposant HTTP/2 ; la bibliothèque standard `urllib` et `httpx`
    restent bloqués en lecture dans cette configuration réseau. `curl` est
    présent par défaut sur Linux et macOS et permet de récupérer réellement les
    données plutôt que de simuler un échec.
    """
    return _curl_transport(url, timeout=timeout, http1=False)


def curl_http1_transport(url: str, *, timeout: int = DEFAULT_TIMEOUT) -> bytes:
    """Variante forçant HTTP/1.1, utile quand le CDN réinitialise les flux HTTP/2."""
    return _curl_transport(url, timeout=timeout, http1=True)


def urllib_transport(url: str, *, timeout: int = URLLIB_TIMEOUT) -> bytes:
    """Transport HTTP de repli basé sur la bibliothèque standard.

    Le délai effectif est borné par `URLLIB_TIMEOUT` : ce transport sert de
    filet de sécurité, il ne doit pas immobiliser la reprise pendant plusieurs
    minutes lorsque `curl` est disponible.
    """
    effective_timeout = min(timeout, URLLIB_TIMEOUT)
    headers = {"User-Agent": USER_AGENT} if USER_AGENT else {}
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=effective_timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        retry_after = exc.headers.get("Retry-After") if exc.headers else None
        raise TransportError(
            f"statut HTTP {exc.code}", status=exc.code, retry_after=retry_after
        ) from exc
    except urllib.error.URLError as exc:
        raise TransportError(f"erreur réseau : {exc.reason}") from exc
    except TimeoutError as exc:
        raise TransportError(f"délai dépassé ({effective_timeout}s)") from exc


def default_transports() -> list[Transport]:
    """Transports utilisés par défaut : `curl` s'il existe, puis `urllib`."""
    transports: list[Transport] = []
    if shutil.which("curl"):
        transports.extend([curl_transport, curl_http1_transport])
    transports.append(urllib_transport)
    return transports


def http_get_bytes(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    transports: list[Transport] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    label: str = "la source",
) -> bytes:
    """Effectue un GET HTTP avec reprise et renvoie le corps de la réponse.

    À chaque tentative, les transports disponibles sont essayés dans l'ordre.
    Les échecs temporaires (délai dépassé, 429, erreur 5xx,réseau) sont
    retentés avec un délai croissant ; un statut 4xx définitif interrompt la
    boucle. L'échec final lève `DataSourceError` avec un message actionnable et
    ne produit jamais de données de remplacement (BR-015).

    Le paramètre `transports` est injectable : les tests l'exploitent pour
    vérifier les erreurs de récupération sans accès réseau.
    """
    candidates = transports if transports is not None else default_transports()
    errors: list[str] = []
    attempt = 0
    while attempt < retries:
        attempt += 1
        for transport in candidates:
            try:
                return transport(url, timeout=timeout)
            except TransportError as exc:
                status = exc.status
                if status is not None and 400 <= status < 500 and status != 429:
                    raise DataSourceError(
                        f"Erreur HTTP {status} en récupérant {label} ({url}). "
                        f"Vérifier l'identifiant de la série, la période demandée et les "
                        f"conditions d'accès du fournisseur ; aucune donnée de "
                        f"remplacement n'est générée."
                    ) from exc
                name = getattr(transport, "__name__", type(transport).__name__)
                errors.append(f"{name}: {exc}")
        if attempt < retries:
            sleep(_retry_delay(attempt, backoff))
    raise DataSourceError(
        f"Échec de récupération pour {label} ({url}) après {retries} tentative(s) : "
        f"{'; '.join(errors[:4])}. Vérifier la connexion Internet, réessayer plus tard "
        f"ou utiliser une copie locale autorisée (--offline). Aucune donnée fictive "
        f"n'est substituée aux données réelles."
    )


def _parse_iso(value: str) -> datetime:
    """Convertit une date ISO (`YYYY-MM-DD`) en datetime UTC (fuseau conservé)."""
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


def _format_iso(value: datetime) -> str:
    """Formate une date au format court `YYYY-MM-DD`."""
    return value.strftime("%Y-%m-%d")


def parse_fred_csv(payload: bytes, spec: SeriesSpec) -> pd.DataFrame:
    """Convertit l'export CSV de FRED en DataFrame (`date`, `close`).

    FRED utilise une valeur vide pour les périodes sans observation : elle est
    convertie en `NaN` et n'est jamais comblée (BR-008).
    """
    text = payload.decode("utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise DataSourceError(f"Réponse CSV vide pour la série {spec.series_id} ({spec.provider}).")
    date_names = {"observation_date", "date"}
    date_column = next((name for name in rows[0] if name.lower() in date_names), None)
    value_column = next((name for name in rows[0] if name not in {date_column, ""}), None)
    if date_column is None or value_column is None:
        raise DataSourceError(
            f"Colonnes inattendues dans la réponse FRED de {spec.series_id} : {list(rows[0])}."
        )
    records = []
    for row in rows:
        raw_value = (row.get(value_column) or "").strip()
        close = float("nan") if raw_value in MISSING_MARKERS else float(raw_value)
        records.append({"date": row[date_column], "close": close})
    frame = pd.DataFrame.from_records(records)
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    if frame["date"].isna().any():
        bad = frame.loc[frame["date"].isna(), "date"].tolist()[:5]
        raise DataSourceError(f"Dates non parsables reçues pour {spec.series_id} : {bad}.")
    frame["close"] = frame["close"].astype("float64")
    return frame


def fetch_fred_series(
    spec: SeriesSpec,
    start: str,
    end: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    transports: list[Transport] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Télécharge une série FRED au format CSV, sans clé API."""
    query = urllib.parse.urlencode({"id": spec.series_id, "cosd": start, "coed": end})
    url = f"{FRED_CSV_ENDPOINT}?{query}"
    payload = http_get_bytes(
        url,
        timeout=timeout,
        retries=retries,
        transports=transports,
        sleep=sleep,
        label=f"FRED/{spec.series_id}",
    )
    frame = parse_fred_csv(payload, spec)
    metadata = _build_metadata(
        spec,
        request_params={"id": spec.series_id, "cosd": start, "coed": end},
        endpoint=url,
        n_rows=len(frame),
        frame=frame,
    )
    return frame, metadata


def parse_coinbase_candles(payload: bytes, spec: SeriesSpec) -> pd.DataFrame:
    """Convertit une réponse de l'API candles Coinbase en DataFrame (`date`, `close`).

    Le schéma documenté est `[time, low, high, open, close, volume]`, où `time`
    est le début de la bougie journalière en secondes UTC. On retient la clôture.
    """
    try:
        payload_json = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise DataSourceError(f"Réponse JSON illisible de {spec.provider} : {exc}") from exc
    if isinstance(payload_json, dict):
        raise DataSourceError(
            f"Réponse inattendue de {spec.provider} : {payload_json.get('message', payload_json)}"
        )
    if not isinstance(payload_json, list) or not payload_json:
        raise DataSourceError(f"Aucune bougie renvoyée par {spec.provider} pour {spec.series_id}.")
    records = [
        {"date": datetime.fromtimestamp(int(item[0]), tz=UTC), "close": float(item[4])}
        for item in payload_json
    ]
    frame = pd.DataFrame.from_records(records)
    frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.tz_convert(None).dt.normalize()
    return frame


def fetch_coinbase_daily_candles(
    spec: SeriesSpec,
    start: str,
    end: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    transports: list[Transport] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    chunk_days: int = COINBASE_CHUNK_DAYS,
    pause: float = 0.35,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Télécharge les bougies journalières BTC-USD par tranches de 290 jours.

    L'API Coinbase refuse toute requête dépassant 300 bougies ; la période est
    donc découpée en fenêtres successives. La documentation indique que
    certaines bougies peuvent précéder le `start` demandé : le filtrage final
    impose la fenêtre exacte.
    """
    start_dt = _parse_iso(start).replace(tzinfo=None)
    end_dt = _parse_iso(end).replace(tzinfo=None) + timedelta(days=1)
    frames: list[pd.DataFrame] = []
    requests_made = 0
    window_start = start_dt
    while window_start < end_dt:
        window_end = min(window_start + timedelta(days=chunk_days), end_dt) - ONE_DAY
        query = urllib.parse.urlencode(
            {
                "granularity": 86400,
                "start": window_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
        )
        url = COINBASE_CANDLES_ENDPOINT.format(product_id=spec.series_id)
        url = f"{url}?{query}"
        payload = http_get_bytes(
            url,
            timeout=timeout,
            retries=retries,
            transports=transports,
            sleep=sleep,
            label=f"Coinbase/{spec.series_id}",
        )
        requests_made += 1
        frames.append(parse_coinbase_candles(payload, spec))
        window_start = window_end + 2 * ONE_DAY
        if window_start < end_dt and pause:
            sleep(pause)

    frame = (
        pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "close"])
    )
    frame = frame.sort_values("date").drop_duplicates(subset="date", keep="last")
    first, last = start_dt, end_dt - ONE_DAY
    mask = (frame["date"] >= first) & (frame["date"] <= last)
    frame = frame.loc[mask].reset_index(drop=True)
    if frame.empty:
        raise DataSourceError(
            f"Aucune bougie BTC-USD reçue entre {start} et {end} : vérifier la période demandée."
        )
    metadata = _build_metadata(
        spec,
        request_params={
            "granularity": 86400,
            "start": start,
            "end": end,
            "chunk_days": chunk_days,
        },
        endpoint=COINBASE_CANDLES_ENDPOINT.format(product_id=spec.series_id),
        n_rows=len(frame),
        frame=frame,
    )
    metadata["http_requests"] = requests_made
    metadata["api_max_candles_per_request"] = COINBASE_MAX_CANDLES
    return frame, metadata


def _build_metadata(
    spec: SeriesSpec,
    *,
    request_params: dict[str, Any],
    endpoint: str,
    n_rows: int,
    frame: pd.DataFrame,
) -> dict[str, Any]:
    """Assemble les métadonnées de collecte (BR-016, BR-019)."""
    return {
        "asset": spec.asset,
        "label": spec.label,
        "provider": spec.provider,
        "series_id": spec.series_id,
        "unit": spec.unit,
        "currency": spec.currency,
        "frequency": spec.frequency,
        "close_convention": spec.close_convention,
        "price_definition": spec.price_definition,
        "source_url": spec.source_url,
        "request_endpoint": endpoint,
        "request_params": request_params,
        "terms_note": spec.terms_note,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows_returned": int(n_rows),
        "first_observation": _format_iso(frame["date"].min().date()) if not frame.empty else None,
        "last_observation": _format_iso(frame["date"].max().date()) if not frame.empty else None,
    }


def fetch_series(
    asset: str,
    start: str,
    end: str,
    *,
    transports: list[Transport] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    retries: int = DEFAULT_RETRIES,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Récupère une série par son identifiant interne (`WTI`, `BTC_USD`, `SP500`).

    Dispatche vers le fournisseur correspondant au registre `SERIES`.
    """
    if asset not in SERIES:
        raise DataSourceError(f"Série inconnue : {asset}. Séries disponibles : {sorted(SERIES)}.")
    spec = SERIES[asset]
    if asset == "BTC_USD":
        return fetch_coinbase_daily_candles(
            spec, start, end, transports=transports, sleep=sleep, retries=retries, timeout=timeout
        )
    return fetch_fred_series(
        spec, start, end, transports=transports, sleep=sleep, retries=retries, timeout=timeout
    )


def fetch_all(
    assets: list[str] | tuple[str, ...],
    start: str,
    end: str,
    *,
    transports: list[Transport] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, tuple[pd.DataFrame, dict[str, Any]]]:
    """Récupère plusieurs séries. La première erreur interrompt la boucle."""
    return {
        asset: fetch_series(asset, start, end, transports=transports, sleep=sleep)
        for asset in assets
    }
