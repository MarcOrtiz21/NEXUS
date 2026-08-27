"""On-demand OHLCV chart series with interval/range-aware disk caching."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from config import CHART_SERIES_CACHE_DIR, CHART_SERIES_CACHE_TTL_SECONDS, CHART_SERIES_POINTS
from data_ingestion import _ohlc_series, _yf_download

_TICKER_RE = re.compile(r"^[A-Z0-9^][A-Z0-9.^=_-]{0,19}$")
_ALIASES = {
    "EURUSD": ("EURUSD", "EURUSD=X"),
    "EURUSD=X": ("EURUSD", "EURUSD=X"),
    "USDEUR": ("USDEUR", "EURUSD=X"),
    "EURCAD": ("EURCAD", "EURCAD=X"),
    "USDCAD": ("USDCAD", "CAD=X"),
    "GBPUSD": ("GBPUSD", "GBPUSD=X"),
    "EURGBP": ("EURGBP", "EURGBP=X"),
    "USDJPY": ("USDJPY", "JPY=X"),
    "USDCHF": ("USDCHF", "CHF=X"),
    "AUDUSD": ("AUDUSD", "AUDUSD=X"),
    "NZDUSD": ("NZDUSD", "NZDUSD=X"),
    "XAUUSD": ("XAUUSD", "GC=F"),
    "XAUUSD=X": ("XAUUSD", "GC=F"),
    "GC=F": ("XAUUSD", "GC=F"),
    "VIX": ("VIX", "^VIX"),
    "^VIX": ("VIX", "^VIX"),
    "SSNLF": ("SSNLF", "005930.KS"),
}
_YF_FALLBACKS = {
    "XAUUSD": ("GC=F", "XAUUSD=X"),
    "EURUSD": ("EURUSD=X",),
    "USDEUR": ("EURUSD=X",),
    "EURCAD": ("EURCAD=X",),
    "USDCAD": ("CAD=X", "USDCAD=X"),
    "GBPUSD": ("GBPUSD=X",),
    "EURGBP": ("EURGBP=X",),
    "USDJPY": ("JPY=X", "USDJPY=X"),
    "USDCHF": ("CHF=X", "USDCHF=X"),
    "AUDUSD": ("AUDUSD=X",),
    "NZDUSD": ("NZDUSD=X",),
    "VIX": ("^VIX", "VIX"),
    "SSNLF": ("005930.KS", "SSNLF"),
}
_FX_SPOT_TICKERS = frozenset({
    "EURUSD", "USDEUR", "EURCAD", "USDCAD", "GBPUSD",
    "EURGBP", "USDJPY", "USDCHF", "AUDUSD", "NZDUSD",
})
_INVERTED_FX_TICKERS = frozenset({"USDEUR"})
SUPPORTED_INTERVALS = ("1m", "5m", "15m", "1h", "4h", "1d", "1wk")
SUPPORTED_RANGES = ("1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y", "5y", "max")
INTERVAL_RANGE_COMPATIBILITY = {
    "1m": frozenset({"1d", "5d"}),
    "5m": frozenset({"1d", "5d", "1mo"}),
    "15m": frozenset({"1d", "5d", "1mo"}),
    "1h": frozenset({"1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y"}),
    "4h": frozenset({"1d", "5d", "1mo", "3mo", "6mo", "ytd", "1y"}),
    "1d": frozenset(SUPPORTED_RANGES),
    "1wk": frozenset(SUPPORTED_RANGES),
}
_FETCH_INTERVAL = {"4h": "1h"}
_FETCH_PERIODS = {
    "1m": {"1d": "1d", "5d": "5d"},
    "5m": {"1d": "5d", "5d": "1mo", "1mo": "1mo"},
    "15m": {"1d": "5d", "5d": "1mo", "1mo": "1mo"},
    "1h": {
        "1d": "1mo", "5d": "1mo", "1mo": "3mo", "3mo": "6mo",
        "6mo": "1y", "ytd": "1y", "1y": "2y",
    },
    "4h": {
        "1d": "1mo", "5d": "1mo", "1mo": "3mo", "3mo": "6mo",
        "6mo": "1y", "ytd": "1y", "1y": "2y",
    },
    "1d": {
        "1d": "1y", "5d": "1y", "1mo": "1y", "3mo": "1y",
        "6mo": "1y", "ytd": "2y", "1y": "2y", "5y": "10y", "max": "max",
    },
    "1wk": {
        "1d": "5y", "5d": "5y", "1mo": "5y", "3mo": "5y",
        "6mo": "5y", "ytd": "5y", "1y": "5y", "5y": "10y", "max": "max",
    },
}
_FIXED_BAR_COUNTS = {
    "1d": {
        "1d": 1, "5d": 5, "1mo": 22, "3mo": 66,
        "6mo": 132, "1y": 252, "5y": 1260,
    },
    "1wk": {"1d": 1, "5d": 1, "1mo": 4, "3mo": 13, "6mo": 26, "1y": 52, "5y": 260},
}


class ChartSeriesUnavailable(RuntimeError):
    """Raised when neither Yahoo nor the local cache can supply a series."""


def normalize_chart_ticker(raw_ticker: str) -> tuple[str, str]:
    """Return the public ticker and its Yahoo Finance ticker."""
    ticker = str(raw_ticker or "").strip().upper()
    if not ticker or not _TICKER_RE.fullmatch(ticker):
        raise ValueError("Ticker no válido")
    return _ALIASES.get(ticker, (ticker, ticker))


def validate_chart_request(interval: str = "1d", range_name: str = "1y") -> tuple[str, str]:
    """Validate and normalize the public interval/range contract."""
    interval = str(interval or "").strip().lower()
    range_name = str(range_name or "").strip().lower()
    if interval not in SUPPORTED_INTERVALS:
        raise ValueError(
            f"Intervalo «{interval}» no válido. Usa: {', '.join(SUPPORTED_INTERVALS)}."
        )
    if range_name not in SUPPORTED_RANGES:
        raise ValueError(
            f"Rango «{range_name}» no válido. Usa: {', '.join(SUPPORTED_RANGES)}."
        )
    allowed = INTERVAL_RANGE_COMPATIBILITY[interval]
    if range_name not in allowed:
        options = ", ".join(item for item in SUPPORTED_RANGES if item in allowed)
        raise ValueError(
            f"Yahoo no admite interval={interval} con range={range_name}. "
            f"Para {interval} usa: {options}."
        )
    return interval, range_name


class ChartSeriesService:
    def __init__(
        self,
        *,
        cache_dir: Path = CHART_SERIES_CACHE_DIR,
        ttl_seconds: int = CHART_SERIES_CACHE_TTL_SECONDS,
        points: int = CHART_SERIES_POINTS,
    ) -> None:
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_seconds
        self.points = points
        self._inflight: dict[tuple[str, str, str], threading.Event] = {}
        self._lock = threading.Lock()

    def get(
        self,
        raw_ticker: str,
        *,
        interval: str = "1d",
        range_name: str = "1y",
        force: bool = False,
    ) -> dict[str, Any]:
        ticker, yf_ticker = normalize_chart_ticker(raw_ticker)
        interval, range_name = validate_chart_request(interval, range_name)
        wanted = [(ticker, yf_ticker)]
        if ticker != "SPY":
            wanted.append(("SPY", "SPY"))

        cached = {
            name: self._load(name, interval, range_name)
            for name, _ in wanted
        }
        missing = [(name, yf_name) for name, yf_name in wanted if cached[name] is None]
        stale = [
            (name, yf_name)
            for name, yf_name in wanted
            if cached[name] is not None and not self._is_fresh(cached[name])
        ]

        if force:
            refreshed, live_keys = self._fetch_and_store(wanted, interval, range_name)
            for name, payload in refreshed.items():
                if payload is not None:
                    cached[name] = payload
            if cached[ticker] is None:
                raise ChartSeriesUnavailable(f"Sin datos de gráfico para {ticker}")
            status = "live" if ticker in live_keys else "stale"
            source = "yahoo_finance" if ticker in live_keys else "cache"
        elif missing:
            refreshed, live_keys = self._fetch_and_store(missing, interval, range_name)
            cached.update(refreshed)
            if cached[ticker] is None:
                raise ChartSeriesUnavailable(f"Sin datos de gráfico para {ticker}")
            status, source = ("live", "yahoo_finance") if ticker in live_keys else ("stale", "cache")
        elif stale:
            self._refresh_in_background(stale, interval, range_name)
            status, source = "stale", "cache"
        else:
            status, source = "fresh", "cache"

        points = list((cached[ticker] or {}).get("points") or [])
        benchmark = list((cached.get("SPY") or {}).get("points") or []) if ticker != "SPY" else []
        points = self._with_relative_spy(points, benchmark)
        as_of = max(
            ((cached[name] or {}).get("as_of") or "" for name, _ in wanted),
            default="",
        ) or None
        revision_input = json.dumps(
            {
                "ticker": ticker, "interval": interval, "range": range_name,
                "points": points, "benchmark": benchmark,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        metadata = cached[ticker] or {}
        return {
            "ticker": ticker,
            "interval": interval,
            "range": range_name,
            "points": points,
            "benchmark": benchmark,
            "as_of": as_of,
            "source": source,
            "status": status,
            "timezone": metadata.get("timezone") or "UTC",
            "session": metadata.get("session") or "regular",
            "adjusted": bool(metadata.get("adjusted", False)),
            "adjustment": metadata.get("adjustment") or "unadjusted",
            "market_state": "unknown",
            "data_status": status,
            "revision": hashlib.sha256(revision_input.encode("utf-8")).hexdigest()[:16],
        }

    def _cache_path(self, ticker: str, interval: str, range_name: str) -> Path:
        safe = re.sub(r"[^a-z0-9]+", "_", ticker.lower()).strip("_")
        identity = f"{ticker}\0{interval}\0{range_name}"
        suffix = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:10]
        return self.cache_dir / safe / interval / f"{range_name}-{suffix}.json"

    def _load(self, ticker: str, interval: str, range_name: str) -> dict[str, Any] | None:
        path = self._cache_path(ticker, interval, range_name)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (
                payload.get("ticker") != ticker
                or payload.get("interval") != interval
                or payload.get("range") != range_name
                or not isinstance(payload.get("points"), list)
            ):
                return None
            return payload
        except (OSError, ValueError, TypeError):
            return None

    def _is_fresh(self, payload: dict[str, Any]) -> bool:
        try:
            fetched_at = datetime.fromisoformat(str(payload["fetched_at"]).replace("Z", "+00:00"))
            if fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - fetched_at).total_seconds() <= self.ttl_seconds
        except (KeyError, TypeError, ValueError):
            return False

    def _fetch_and_store(
        self,
        wanted: list[tuple[str, str]],
        interval: str,
        range_name: str,
    ) -> tuple[dict[str, dict[str, Any] | None], set[str]]:
        if not wanted:
            return {}, set()
        owned: list[tuple[str, str]] = []
        waiting: list[tuple[str, threading.Event]] = []
        with self._lock:
            for ticker, yf_ticker in wanted:
                key = (ticker, interval, range_name)
                event = self._inflight.get(key)
                if event is None:
                    event = threading.Event()
                    self._inflight[key] = event
                    owned.append((ticker, yf_ticker))
                else:
                    waiting.append((ticker, event))

        result: dict[str, dict[str, Any] | None] = {}
        live_keys: set[str] = set()
        try:
            if owned:
                frame = _yf_download(
                    [yf_ticker for _, yf_ticker in owned],
                    period=_FETCH_PERIODS[interval][range_name],
                    interval=_FETCH_INTERVAL.get(interval, interval),
                )
                fetched_at = datetime.now(timezone.utc).isoformat()
                for ticker, yf_ticker in owned:
                    points, metadata = self._frame_points(
                        frame, ticker, yf_ticker, interval, range_name
                    )
                    used_yf = yf_ticker
                    if not points:
                        retry_symbols = [yf_ticker]
                        for alt in _YF_FALLBACKS.get(ticker, ()):
                            if alt not in retry_symbols:
                                retry_symbols.append(alt)
                        if len(owned) == 1:
                            retry_symbols = [symbol for symbol in retry_symbols if symbol != yf_ticker]
                        for alt in retry_symbols:
                            alt_frame = _yf_download(
                                [alt],
                                period=_FETCH_PERIODS[interval][range_name],
                                interval=_FETCH_INTERVAL.get(interval, interval),
                            )
                            points, metadata = self._frame_points(
                                alt_frame, ticker, alt, interval, range_name
                            )
                            if points:
                                used_yf = alt
                                break
                    if not points:
                        result[ticker] = self._load(ticker, interval, range_name)
                        continue
                    payload = {
                        "schema": 2,
                        "ticker": ticker,
                        "yf_ticker": used_yf,
                        "interval": interval,
                        "range": range_name,
                        "points": points,
                        "as_of": points[-1]["date"],
                        "fetched_at": fetched_at,
                        **metadata,
                    }
                    self._save(ticker, interval, range_name, payload)
                    result[ticker] = payload
                    live_keys.add(ticker)
        finally:
            with self._lock:
                for ticker, _ in owned:
                    event = self._inflight.pop((ticker, interval, range_name), None)
                    if event is not None:
                        event.set()

        for ticker, event in waiting:
            event.wait()
            result[ticker] = self._load(ticker, interval, range_name)
        return result, live_keys

    def _save(
        self,
        ticker: str,
        interval: str,
        range_name: str,
        payload: dict[str, Any],
    ) -> None:
        path = self._cache_path(ticker, interval, range_name)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)

    def _refresh_in_background(
        self,
        wanted: list[tuple[str, str]],
        interval: str,
        range_name: str,
    ) -> None:
        def refresh() -> None:
            self._fetch_and_store(wanted, interval, range_name)

        threading.Thread(target=refresh, name="nexus-chart-refresh", daemon=True).start()

    def _frame_points(
        self,
        frame: pd.DataFrame | None,
        ticker: str,
        yf_ticker: str,
        interval: str,
        range_name: str,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if frame is None:
            return [], {}
        candidates = (yf_ticker,) + tuple(
            alt for alt in _YF_FALLBACKS.get(ticker, ()) if alt != yf_ticker
        )
        series = None
        for candidate in candidates:
            series = {
                field.lower(): _ohlc_series(frame, field, candidate)
                for field in ("Open", "High", "Low", "Close", "Volume")
            }
            if series["close"] is not None and not series["close"].dropna().empty:
                break
        if series is None or series["close"] is None or not isinstance(series["close"], pd.Series):
            return [], {}
        if series["close"].dropna().empty:
            return [], {}
        data = pd.DataFrame({
            key: value for key, value in series.items()
            if isinstance(value, pd.Series)
        })
        if "close" not in data.columns:
            return [], {}
        data = data.dropna(subset=["close"]).sort_index()
        if data.empty:
            return [], {}
        if ticker in _INVERTED_FX_TICKERS:
            original_open = data.get("open")
            original_high = data.get("high")
            original_low = data.get("low")
            data["close"] = 1 / data["close"]
            if original_open is not None:
                data["open"] = 1 / original_open
            if original_low is not None:
                data["high"] = 1 / original_low
            if original_high is not None:
                data["low"] = 1 / original_high
        if interval == "4h":
            data = self._aggregate_four_hour(data)
        data["ma20"] = data["close"].rolling(20, min_periods=20).mean()
        data["ma50"] = data["close"].rolling(50, min_periods=50).mean()
        data["ma200"] = data["close"].rolling(200, min_periods=200).mean()
        data = self._apply_range(data, interval, range_name)
        if self.points > 0 and interval == "1d" and range_name == "1y":
            data = data.tail(max(self.points, 252))

        timezone_name = self._timezone_name(data.index, ticker)
        session = "24x5" if ticker in _FX_SPOT_TICKERS else "regular"
        decimals = 3 if ticker == "USDJPY" else (5 if ticker in _FX_SPOT_TICKERS else 2)
        points: list[dict[str, Any]] = []
        for idx, row in data.iterrows():
            timestamp = pd.Timestamp(idx)
            if timestamp.tzinfo is None:
                timestamp = timestamp.tz_localize(ZoneInfo(timezone_name))
            utc_timestamp = timestamp.tz_convert(timezone.utc)
            date = (
                timestamp.strftime("%Y-%m-%d")
                if interval in {"1d", "1wk"}
                else timestamp.isoformat()
            )

            def number(field: str, *, precision: int = decimals) -> float | None:
                value = row.get(field)
                return None if value is None or pd.isna(value) else round(float(value), precision)

            close_value = number("close")
            open_value, high_value, low_value = number("open"), number("high"), number("low")
            synthetic = any(value is None for value in (open_value, high_value, low_value))
            volume = None if ticker in _FX_SPOT_TICKERS else number("volume", precision=0)
            points.append({
                "date": date,
                "epoch": int(utc_timestamp.timestamp()),
                "open": open_value if open_value is not None else close_value,
                "high": high_value if high_value is not None else close_value,
                "low": low_value if low_value is not None else close_value,
                "close": close_value,
                "value": close_value,
                "volume": volume,
                "ma20": number("ma20"),
                "ma50": number("ma50"),
                "ma200": number("ma200"),
                "synthetic_ohlc": synthetic,
                "interval": interval,
                "timezone": timezone_name,
                "session": session,
                "adjusted": False,
                "adjustment": "unadjusted",
            })
        return points, {
            "timezone": timezone_name,
            "session": session,
            "adjusted": False,
            "adjustment": "unadjusted",
        }

    @staticmethod
    def _aggregate_four_hour(data: pd.DataFrame) -> pd.DataFrame:
        """Aggregate each trading day's 1h bars without crossing sessions."""
        local_dates = pd.Index(data.index).date
        positions = pd.Series(range(len(data)), index=data.index)
        groups = positions.groupby(local_dates).cumcount() // 4
        keys = [local_dates, groups.to_numpy()]
        aggregations: dict[str, Any] = {
            "open": "first", "high": "max", "low": "min", "close": "last",
            "volume": lambda values: values.sum(min_count=1),
        }
        aggregated = data.groupby(keys, sort=True).agg(aggregations)
        last_index = data.groupby(keys, sort=True).apply(lambda chunk: chunk.index[-1])
        aggregated.index = pd.DatetimeIndex(last_index.to_list())
        return aggregated

    @staticmethod
    def _apply_range(data: pd.DataFrame, interval: str, range_name: str) -> pd.DataFrame:
        fixed = _FIXED_BAR_COUNTS.get(interval, {}).get(range_name)
        if fixed is not None:
            return data.tail(fixed)
        if range_name == "max":
            return data
        latest = pd.Timestamp(data.index[-1])
        if range_name == "ytd":
            cutoff = pd.Timestamp(year=latest.year, month=1, day=1, tz=latest.tz)
        else:
            offsets = {
                "1d": pd.DateOffset(days=1), "5d": pd.DateOffset(days=5),
                "1mo": pd.DateOffset(months=1), "3mo": pd.DateOffset(months=3),
                "6mo": pd.DateOffset(months=6), "1y": pd.DateOffset(years=1),
                "5y": pd.DateOffset(years=5),
            }
            cutoff = latest - offsets[range_name]
        return data.loc[data.index >= cutoff]

    @staticmethod
    def _timezone_name(index: pd.Index, ticker: str) -> str:
        tz = getattr(index, "tz", None)
        if tz is not None:
            return str(tz)
        return "UTC" if ticker in _FX_SPOT_TICKERS else "America/New_York"

    @staticmethod
    def _with_relative_spy(points: list[dict], benchmark: list[dict]) -> list[dict]:
        if not points or not benchmark:
            return [dict(point, rel_spy=None) for point in points]
        spy_by_epoch = {point.get("epoch"): point.get("value") for point in benchmark}
        spy_by_date = {str(point.get("date"))[:10]: point.get("value") for point in benchmark}
        first_match = next(
            (
                point for point in points
                if spy_by_epoch.get(point.get("epoch"))
                or spy_by_date.get(str(point.get("date"))[:10])
            ),
            None,
        )
        base = (first_match or {}).get("value")
        spy_base = (
            spy_by_epoch.get((first_match or {}).get("epoch"))
            or spy_by_date.get(str((first_match or {}).get("date"))[:10])
        )
        if not base or not spy_base:
            return [dict(point, rel_spy=None) for point in points]
        output = []
        for point in points:
            spy_value = (
                spy_by_epoch.get(point.get("epoch"))
                or spy_by_date.get(str(point.get("date"))[:10])
            )
            relative = None
            if point.get("value") and spy_value:
                relative = round(
                    ((float(point["value"]) / float(base)) - (float(spy_value) / float(spy_base))) * 100,
                    2,
                )
            output.append(dict(point, rel_spy=relative))
        return output


chart_series_service = ChartSeriesService()
