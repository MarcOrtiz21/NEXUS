"""
Módulo de Ingesta de Datos (data_ingestion.py)

Encargado de las conexiones API para la extracción de datos brutos del mercado.
Extrae VIX, Bonos, Correlación Sectorial, PER del S&P 500,
y opcionalmente M2 (Liquidez) e IPC (Inflación) vía FRED API.
"""

import yfinance as yf
import pandas as pd
import numpy as np
import requests
import logging
import json
import os
import signal
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from itertools import combinations

from config import (
    FRED_API_KEY,
    MARKET_CACHE_FILE,
    MARKET_CACHE_MAX_AGE_SECONDS,
    FAST_MARKET_CACHE_FILE,
    SLOW_MACRO_CACHE_FILE,
    ROTATION_MARKET_CACHE_FILE,
    FAST_MARKET_CACHE_TTL_SECONDS,
    SLOW_MACRO_CACHE_TTL_SECONDS,
    ROTATION_MARKET_CACHE_TTL_SECONDS,
    GLOBAL_MARKET_TICKERS,
    PE_PERCENTILE_HIGH,
    PE_PERCENTILE_LOW,
    YFINANCE_TIMEOUT_SECONDS,
    SANITY_FX_PRODUCT_TOL,
    SANITY_SPY_IVV_PCT,
    SANITY_VIX_MAX,
    SANITY_VIX_MIN,
)
from rotation_catalog import ROTATION_COMPANY_TICKERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
    force=True,
)

# ETFs sectoriales para correlación media (10 pares posibles).
SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLE", "XLP"]

# Activos usados por la capa de decisión final.
DECISION_ASSETS = ["SPY", "QQQ", "TLT", "GLD", "UUP"]

# Proxies usados para detectar rotación sectorial/temática.
ROTATION_ASSETS = [
    "XLK", "SMH", "SOXX", "IGV", "AIQ", "FIVG", "SRVR", "GRID", "VRT",
    "SKYY", "CIBR", "XLV", "XBI", "PJP", "KIE", "KBE", "XLI", "ITA",
    "XLY", "XLU", "XLB", "XLE",
    "EWJ", "FXI", "AAXJ", "EWY", "EWP",
]

# Par principal de divisas para bloque FX.
FOREX_TICKERS = {"EURUSD": "EURUSD=X"}

FAST_CACHE_KEYS = (
    "VIX", "VIX_MA5", "VIX_MA10", "VIX_MA20", "US10Y", "Correlation_Proxy",
    "Assets", "RotationAssets", "Forex", "GlobalMarkets", "PriceSparklines",
    "CrossPrices",
)
SPARKLINE_POINTS = 252

ROTATION_CACHE_KEYS = ("RotationCompanies",)

# Cambia cuando se modifica el contrato de los bloques cacheados. Así no se
# reutiliza un cache antiguo que, por ejemplo, no contiene nuevos proxies.
CACHE_SCHEMA_VERSION = 9
MIN_USABLE_CACHE_SCHEMA = 6
CACHE_METRIC_GROUPS = {"Assets", "RotationAssets", "RotationCompanies", "Forex", "GlobalMarkets"}

SLOW_VALUE_KEYS = (
    "US2Y", "Yield_Curve_Spread", "M2_Latest", "M2_Previous", "M2_Change_Pct",
    "CPI_Latest", "CPI_YoY_Pct", "China_M2_YoY_Pct",
    "PE_Trailing", "PE_Forward", "PE_Forward_Date", "PE_Forward_Source", "PE_Forward_Percentile",
)
SLOW_ASOF_KEYS = ("M2_AsOf", "CPI_AsOf", "China_M2_AsOf", "US2Y_AsOf")
SLOW_CACHE_KEYS = SLOW_VALUE_KEYS + SLOW_ASOF_KEYS
_ASOF_FOR_KEY = {
    "CPI_YoY_Pct": "CPI_AsOf",
    "CPI_Latest": "CPI_AsOf",
    "M2_Change_Pct": "M2_AsOf",
    "M2_Latest": "M2_AsOf",
    "China_M2_YoY_Pct": "China_M2_AsOf",
    "US2Y": "US2Y_AsOf",
}


# ─────────────────────────────────────────────────────────────
# Funciones auxiliares
# ─────────────────────────────────────────────────────────────

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quality(
    source: str,
    status: str = "OK",
    captured_at: str | None = None,
    detail: str = "",
    *,
    as_of: str | None = None,
) -> Dict[str, str]:
    payload = {
        "source": source,
        "status": status,
        "captured_at": captured_at or _now_utc_iso(),
        "detail": detail,
    }
    if as_of:
        payload["as_of"] = as_of
    return payload


def _mark_quality(
    data: Dict[str, Any],
    key: str,
    source: str,
    status: str = "OK",
    detail: str = "",
    captured_at: str | None = None,
    as_of: str | None = None,
) -> None:
    data.setdefault("DataQuality", {})[key] = _quality(
        source, status, captured_at=captured_at, detail=detail, as_of=as_of
    )


def _find_obs_near_date(observations: list, target_date: str) -> float | None:
    """Busca la última observación disponible hasta target_date, sin mirar al futuro."""
    if not observations:
        return None
    best = None
    target = datetime.strptime(target_date, "%Y-%m-%d")
    best_date = None
    for obs in observations:
        try:
            obs_date = datetime.strptime(obs["date"], "%Y-%m-%d")
            if obs_date <= target and (best_date is None or obs_date > best_date):
                best_date = obs_date
                best = obs["value"]
        except (TypeError, ValueError, KeyError):
            continue
    return best


def _parse_captured_at(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _payload_age_seconds(payload: Dict[str, Any], mtime_age: float) -> float:
    """Edad del bloque: captured_at persistido, no el mtime de un rewrite ajeno."""
    captured = _parse_captured_at(payload.get("captured_at"))
    if captured is None:
        return float(mtime_age)
    return max(0.0, datetime.now(timezone.utc).timestamp() - captured.timestamp())


def _load_market_cache() -> Dict[str, Any] | None:
    if not MARKET_CACHE_FILE.exists():
        return None
    try:
        age = datetime.now(timezone.utc).timestamp() - MARKET_CACHE_FILE.stat().st_mtime
        payload = json.loads(MARKET_CACHE_FILE.read_text(encoding="utf-8"))
        payload["_cache_age_seconds"] = _payload_age_seconds(payload, age)
        return payload
    except Exception as e:
        logging.warning(f"No se pudo leer cache de mercado: {e}")
        return None


def _save_market_cache(data: Dict[str, Any]) -> None:
    try:
        MARKET_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = MARKET_CACHE_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(MARKET_CACHE_FILE)
    except Exception as e:
        logging.warning(f"No se pudo guardar cache de mercado: {e}")


def _apply_cache_fallback(data: Dict[str, Any], cache: Dict[str, Any] | None) -> Dict[str, Any]:
    if not cache:
        return data

    cache_age = cache.get("_cache_age_seconds")
    stale = cache_age is None or cache_age > MARKET_CACHE_MAX_AGE_SECONDS
    for key, value in cache.items():
        if key.startswith("_") or key in {"DataQuality", "schema_version"}:
            continue
        status = "STALE" if stale else "OK"
        detail = "fallback desde cache local"
        if key in CACHE_METRIC_GROUPS:
            _merge_metric_group_from_cache(data, key, value, status, detail)
            continue
        should_fallback = data.get(key) in (None, {})
        if should_fallback and value not in (None, {}):
            data[key] = value
            _mark_quality(data, key, "cache", status, detail)

    return data


def _load_tier_cache(path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_cache_age_seconds"] = _payload_age_seconds(payload, age)
        return payload
    except Exception as exc:
        logging.warning(f"No se pudo leer cache {path.name}: {exc}")
        return None


def _save_tier_cache(
    path,
    payload: Dict[str, Any],
    *,
    captured_at: str | None = None,
    source: str | None = None,
) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = {k: v for k, v in payload.items() if not k.startswith("_")}
        clean["schema_version"] = CACHE_SCHEMA_VERSION
        clean["captured_at"] = captured_at or payload.get("captured_at") or _now_utc_iso()
        if source or payload.get("source"):
            clean["source"] = source or payload.get("source")
        tmp = path.with_suffix('.tmp')
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(path)
    except Exception as exc:
        logging.warning(f"No se pudo guardar cache {path.name}: {exc}")


def _cache_is_fresh(cache: Dict[str, Any] | None, ttl_seconds: int) -> bool:
    if not cache:
        return False
    age = cache.get("_cache_age_seconds")
    return age is not None and age <= ttl_seconds


def _apply_tier_cache(data: Dict[str, Any], cache: Dict[str, Any] | None, keys: tuple[str, ...], stale: bool) -> None:
    if not cache:
        return
    for key in keys:
        value = cache.get(key)
        if value in (None, {}):
            continue
        status = "STALE" if stale else "OK"
        stamp = cache.get("captured_at") if isinstance(cache.get("captured_at"), str) else None
        source = str(cache.get("source") or "cache")
        detail = f"desde cache ({'stale' if stale else 'fresh'})"
        as_of_key = _ASOF_FOR_KEY.get(key)
        as_of = cache.get(as_of_key) if as_of_key else None
        as_of = as_of if isinstance(as_of, str) else None
        if key in CACHE_METRIC_GROUPS:
            _merge_metric_group_from_cache(data, key, value, status, detail, captured_at=stamp, source=source)
        else:
            data[key] = value
            _mark_quality(data, key, source, status, detail, captured_at=stamp, as_of=as_of)
    cache_age = cache.get("_cache_age_seconds")
    if isinstance(cache_age, (int, float)):
        current_age = data.get("_cache_age_seconds")
        data["_cache_age_seconds"] = max(float(current_age or 0), float(cache_age))


def _merge_metric_group_from_cache(
    data: Dict[str, Any],
    key: str,
    cached_group: Any,
    status: str,
    detail: str,
    captured_at: str | None = None,
    source: str = "cache",
) -> None:
    """Completa solo métricas ausentes; nunca pisa una lectura recién obtenida."""
    current_group = data.get(key)
    if not isinstance(current_group, dict) or not isinstance(cached_group, dict):
        return

    merged = dict(current_group)
    for name, cached_metrics in cached_group.items():
        if not isinstance(cached_metrics, dict):
            continue
        current_metrics = merged.get(name)
        metrics = dict(current_metrics) if isinstance(current_metrics, dict) else {}
        used_cache = False
        for metric, cached_value in cached_metrics.items():
            if metrics.get(metric) is None and cached_value is not None:
                metrics[metric] = cached_value
                used_cache = True
        if used_cache:
            merged[name] = metrics
            _mark_quality(data, f"{key}.{name}", source, status, detail, captured_at=captured_at)
    data[key] = merged


def _extract_tier_payload(data: Dict[str, Any], keys: tuple[str, ...]) -> Dict[str, Any]:
    return {key: data.get(key) for key in keys if data.get(key) not in (None, {})}


def _cache_schema_ok(cache: Dict[str, Any] | None) -> bool:
    version = (cache or {}).get("schema_version")
    return isinstance(version, int) and version >= MIN_USABLE_CACHE_SCHEMA


def _fast_cache_complete(cache: Dict[str, Any] | None) -> bool:
    """Campos mínimos para pintar la UI, sin exigir frescura."""
    if not _cache_schema_ok(cache):
        return False
    assets = (cache or {}).get("Assets", {})
    forex = (cache or {}).get("Forex", {})
    global_markets = (cache or {}).get("GlobalMarkets", {})
    return (
        cache.get("VIX") is not None
        and assets.get("SPY", {}).get("price") is not None
        and assets.get("GLD", {}).get("price") is not None
        and forex.get("EURUSD", {}).get("price") is not None
        and any(metrics.get("price") is not None for metrics in global_markets.values())
    )


def _rotation_cache_complete(cache: Dict[str, Any] | None) -> bool:
    if not _cache_schema_ok(cache):
        return False
    companies = (cache or {}).get("RotationCompanies", {})
    return any(metrics.get("price") is not None for metrics in companies.values())


def _slow_cache_complete(cache: Dict[str, Any] | None) -> bool:
    if not _cache_schema_ok(cache):
        return False
    return any((cache or {}).get(key) is not None for key in SLOW_VALUE_KEYS)


def _fast_cache_usable(cache: Dict[str, Any] | None) -> bool:
    return _cache_is_fresh(cache, FAST_MARKET_CACHE_TTL_SECONDS) and _fast_cache_complete(cache)


def _rotation_cache_usable(cache: Dict[str, Any] | None) -> bool:
    """Indica si el detalle de empresas puede servirse sin otra descarga."""
    return _cache_is_fresh(cache, ROTATION_MARKET_CACHE_TTL_SECONDS) and _rotation_cache_complete(cache)


def _slow_cache_usable(cache: Dict[str, Any] | None) -> bool:
    return _cache_is_fresh(cache, SLOW_MACRO_CACHE_TTL_SECONDS) and _slow_cache_complete(cache)


def _layer_freshness(
    label: str,
    cache: Dict[str, Any] | None,
    *,
    live: bool,
    present: bool,
    ttl: int,
) -> Dict[str, Any]:
    """Edad de una capa de datos: live=0, caché con TTL, o ausente."""
    if live:
        return {"label": label, "age_seconds": 0, "status": "OK", "ttl_seconds": ttl}
    if not present:
        return {"label": label, "age_seconds": None, "status": "MISSING", "ttl_seconds": ttl}
    age = (cache or {}).get("_cache_age_seconds")
    if not isinstance(age, (int, float)):
        return {"label": label, "age_seconds": None, "status": "UNKNOWN", "ttl_seconds": ttl}
    status = "OK" if age <= ttl else "STALE"
    return {"label": label, "age_seconds": int(round(age)), "status": status, "ttl_seconds": ttl}


def _run_isolated(code: str, timeout: int) -> int:
    """Ejecuta código en un proceso aparte y lo mata si se pasa de tiempo.

    yfinance no respeta timeouts de requests: hay que cortar el proceso.
    subprocess (no multiprocessing) funciona desde el threadpool de FastAPI.
    """
    proc = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        start_new_session=True,
        cwd=str(Path(__file__).resolve().parent),
    )
    try:
        proc.wait(timeout=timeout)
        return int(proc.returncode or 0)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            proc.kill()
        try:
            proc.wait(timeout=2)
        except Exception:
            pass
        return -9


def _yf_download_job(
    tickers: list[str],
    period: str,
    output_path: str,
    interval: str = "1d",
) -> None:
    """Proceso aparte para poder matarlo si Yahoo no responde."""
    import pandas as pd
    import yfinance as yf

    frame = yf.download(
        tickers,
        period=period,
        interval=interval,
        progress=False,
        threads=False,
        auto_adjust=False,
    )
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return
    frame.to_pickle(output_path)


def _yf_download(
    tickers: list[str],
    period: str = "2y",
    timeout: int = YFINANCE_TIMEOUT_SECONDS,
    interval: str = "1d",
):
    """Descarga yfinance con tope de tiempo real. Si vence, se mata el proceso."""
    if not tickers:
        return None
    handle = tempfile.NamedTemporaryFile(suffix=".pkl", delete=False)
    output_path = handle.name
    handle.close()
    try:
        rc = _run_isolated(
            "from data_ingestion import _yf_download_job; "
            f"_yf_download_job({list(tickers)!r}, {period!r}, {output_path!r}, {interval!r})",
            timeout,
        )
        if rc != 0 or not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
            if rc == -9:
                logging.warning(f"yfinance superó {timeout}s; se mantiene la caché local si existe.")
            return None
        return pd.read_pickle(output_path)
    except Exception as exc:
        logging.error(f"Fallo en yfinance: {exc}")
        return None
    finally:
        try:
            Path(output_path).unlink(missing_ok=True)
        except Exception:
            pass


def _sparkline_points(series: pd.Series, spy: pd.Series | None = None, points: int = SPARKLINE_POINTS) -> list[dict]:
    closes = series.dropna().tail(points)
    if closes.empty:
        return []
    spy_aligned = spy.dropna().reindex(closes.index).ffill() if spy is not None else None
    base = float(closes.iloc[0])
    spy_base = None
    if spy_aligned is not None and not spy_aligned.empty and pd.notna(spy_aligned.iloc[0]) and float(spy_aligned.iloc[0]):
        spy_base = float(spy_aligned.iloc[0])
    out: list[dict] = []
    for idx, value in closes.items():
        px = float(value)
        rel = None
        if spy_aligned is not None and spy_base and base:
            spy_px = spy_aligned.loc[idx] if idx in spy_aligned.index else None
            if spy_px is not None and pd.notna(spy_px) and float(spy_px):
                rel = round(((px / base) - (float(spy_px) / spy_base)) * 100, 2)
        date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        out.append({"date": date, "value": round(px, 4), "rel_spy": rel})
    return out


def _ohlc_series(df: pd.DataFrame, field: str, ticker: str) -> pd.Series | None:
    if df is None or df.empty or not ticker:
        return None
    try:
        if isinstance(df.columns, pd.MultiIndex):
            if field in df.columns.get_level_values(0):
                chunk = df[field]
                series = _single_ohlc_column(chunk, ticker)
                if series is not None:
                    return series
            if ticker in df.columns.get_level_values(0):
                chunk = df[ticker]
                series = _single_ohlc_column(chunk, field)
                if series is not None:
                    return series
        if field in df.columns:
            return df[field]
    except Exception:
        return None
    return None


def _single_ohlc_column(chunk: pd.Series | pd.DataFrame, name: str) -> pd.Series | None:
    if isinstance(chunk, pd.Series):
        return chunk
    if not isinstance(chunk, pd.DataFrame) or chunk.empty:
        return None
    if name in chunk.columns:
        extracted = chunk[name]
        return extracted if isinstance(extracted, pd.Series) else None
    return None


def _ohlc_sparkline_points(
    df: pd.DataFrame,
    ticker: str,
    spy: pd.Series | None = None,
    points: int = SPARKLINE_POINTS,
    decimals: int = 4,
) -> list[dict]:
    close = _ohlc_series(df, "Close", ticker)
    if close is None:
        return []
    close = close.dropna()
    if close.empty:
        return []
    open_s = _ohlc_series(df, "Open", ticker)
    high_s = _ohlc_series(df, "High", ticker)
    low_s = _ohlc_series(df, "Low", ticker)
    ma20 = close.rolling(20, min_periods=20).mean()
    window = close.tail(points)
    spy_aligned = spy.dropna().reindex(window.index).ffill() if spy is not None else None
    base = float(window.iloc[0])
    spy_base = None
    if spy_aligned is not None and not spy_aligned.empty and pd.notna(spy_aligned.iloc[0]) and float(spy_aligned.iloc[0]):
        spy_base = float(spy_aligned.iloc[0])

    out: list[dict] = []
    for idx, value in window.items():
        px = float(value)

        def _px(series: pd.Series | None) -> float | None:
            if series is None:
                return None
            try:
                raw = series.loc[idx]
            except Exception:
                return None
            if raw is None or pd.isna(raw):
                return None
            return round(float(raw), decimals)

        rel = None
        if spy_aligned is not None and spy_base and base:
            spy_px = spy_aligned.loc[idx] if idx in spy_aligned.index else None
            if spy_px is not None and pd.notna(spy_px) and float(spy_px):
                rel = round(((px / base) - (float(spy_px) / spy_base)) * 100, 2)
        ma = _px(ma20)
        open_px, high_px, low_px = _px(open_s), _px(high_s), _px(low_s)
        synthetic_ohlc = any(value is None for value in (open_px, high_px, low_px))
        date = idx.strftime("%Y-%m-%d") if hasattr(idx, "strftime") else str(idx)[:10]
        out.append({
            "date": date,
            "value": round(px, decimals),
            "open": open_px if open_px is not None else round(px, decimals),
            "high": high_px if high_px is not None else round(px, decimals),
            "low": low_px if low_px is not None else round(px, decimals),
            "ma20": ma,
            "rel_spy": rel,
            "synthetic_ohlc": synthetic_ohlc,
        })
    return out


def _sparkline_alias(ticker: str) -> str:
    aliases = {"EURUSD=X": "EURUSD", "^VIX": "VIX"}
    for pair, yf_ticker in FOREX_TICKERS.items():
        aliases[str(yf_ticker)] = pair
    return aliases.get(ticker, ticker)


def _sparkline_decimals(alias: str) -> int:
    return 5 if alias == "EURUSD" else 2


def _sparkline_universe() -> set[str]:
    return set(
        DECISION_ASSETS
        + ROTATION_ASSETS
        + list(FOREX_TICKERS.values())
        + list(GLOBAL_MARKET_TICKERS.values())
        + ["^VIX", "SPY"]
    )


def _build_ohlc_sparklines(
    df: pd.DataFrame,
    df_close: pd.DataFrame | None = None,
    tickers: list[str] | None = None,
) -> Dict[str, list]:
    spy = None
    if df_close is not None and "SPY" in df_close.columns:
        spy = df_close["SPY"].dropna()
    result: Dict[str, list] = {}
    for yf_ticker in tickers or _sparkline_universe():
        alias = _sparkline_alias(str(yf_ticker))
        points = _ohlc_sparkline_points(
            df,
            str(yf_ticker),
            spy=spy if alias != "SPY" else None,
            decimals=_sparkline_decimals(alias),
        )
        if points:
            result[alias] = points
    return result


def _build_sparklines(df_close: pd.DataFrame, tickers: list[str] | None = None) -> Dict[str, list]:
    spy = df_close["SPY"].dropna() if "SPY" in df_close.columns else None
    wanted = list(tickers) if tickers is not None else list(_sparkline_universe())
    result: Dict[str, list] = {}
    for ticker in wanted:
        if ticker not in df_close.columns:
            continue
        alias = _sparkline_alias(ticker)
        points = _sparkline_points(df_close[ticker], spy if alias != "SPY" else None)
        if points:
            result[alias] = points
    return result


def _calculate_sector_correlation(df_close: pd.DataFrame, etfs: list, window: int = 20) -> float | None:
    """Correlación media de retornos diarios entre todos los pares de ETFs sectoriales."""
    available = [e for e in etfs if e in df_close.columns]
    if len(available) < 2:
        return None

    returns = df_close[available].pct_change().dropna().tail(window)
    if len(returns) < 10:
        return None

    correlations = []
    for a, b in combinations(available, 2):
        c = returns[a].corr(returns[b])
        if not np.isnan(c):
            correlations.append(c)

    return float(np.mean(correlations)) if correlations else None


def _calculate_asset_metrics(df_close: pd.DataFrame, ticker: str) -> Dict[str, float | None]:
    """Calcula métricas simples de tendencia, momentum y volatilidad para un ETF."""
    metrics = {
        "price": None,
        "ma20": None,
        "ma50": None,
        "ma200": None,
        "momentum_1m": None,
        "momentum_3m": None,
        "volatility_20d": None,
    }

    if ticker not in df_close.columns:
        return metrics

    series = df_close[ticker].dropna()
    if series.empty:
        return metrics

    metrics["price"] = float(series.iloc[-1])
    if len(series) >= 20:
        metrics["ma20"] = float(series.tail(20).mean())
        returns = series.pct_change().dropna().tail(20)
        if not returns.empty:
            metrics["volatility_20d"] = float(returns.std() * np.sqrt(252) * 100)
    if len(series) >= 50:
        metrics["ma50"] = float(series.tail(50).mean())
    if len(series) >= 200:
        metrics["ma200"] = float(series.tail(200).mean())
    if len(series) >= 22:
        base = series.iloc[-22]
        if base > 0:
            metrics["momentum_1m"] = float(((series.iloc[-1] - base) / base) * 100)
    if len(series) >= 64:
        base = series.iloc[-64]
        if base > 0:
            metrics["momentum_3m"] = float(((series.iloc[-1] - base) / base) * 100)

    return metrics


def _close_last(df_close: pd.DataFrame, ticker: str) -> float | None:
    if df_close is None or ticker not in df_close.columns:
        return None
    series = df_close[ticker].dropna()
    if series.empty:
        return None
    return float(series.iloc[-1])


def _apply_cross_sanity(data: Dict[str, Any]) -> list[str]:
    """Cruza fuentes hermanas. Si divergen, marca MISSING y no deja puntuar el print raro."""
    rejected: list[str] = []
    vix = data.get("VIX")
    if isinstance(vix, (int, float)) and not (SANITY_VIX_MIN <= float(vix) <= SANITY_VIX_MAX):
        data["VIX"] = None
        for key in ("VIX_MA5", "VIX_MA10", "VIX_MA20"):
            data[key] = None
        _mark_quality(
            data, "VIX", "sanity:^VIX", "MISSING",
            f"saneamiento cruzado: VIX {vix:.1f} fuera de rango {SANITY_VIX_MIN:.0f}–{SANITY_VIX_MAX:.0f}",
        )
        rejected.append("VIX")

    cross = data.get("CrossPrices") if isinstance(data.get("CrossPrices"), dict) else {}
    spy = (data.get("Assets") or {}).get("SPY") or {}
    spy_px = spy.get("price")
    ivv_px = cross.get("IVV")
    if (
        isinstance(spy_px, (int, float)) and spy_px > 0
        and isinstance(ivv_px, (int, float)) and ivv_px > 0
    ):
        gap = abs(spy_px / ivv_px - 1.0) * 100
        if gap > SANITY_SPY_IVV_PCT:
            spy = dict(spy)
            spy["price"] = None
            data.setdefault("Assets", {})["SPY"] = spy
            _mark_quality(
                data, "Assets.SPY", "sanity:SPY/IVV", "MISSING",
                f"saneamiento cruzado: SPY vs IVV diverge {gap:.1f}%",
            )
            rejected.append("SPY")

    fx = (data.get("Forex") or {}).get("EURUSD") or {}
    eur = fx.get("price")
    usd = cross.get("USDEUR")
    if isinstance(eur, (int, float)) and eur > 0 and isinstance(usd, (int, float)) and usd > 0:
        product = eur * usd
        if abs(product - 1.0) > SANITY_FX_PRODUCT_TOL:
            fx = dict(fx)
            fx["price"] = None
            data.setdefault("Forex", {})["EURUSD"] = fx
            _mark_quality(
                data, "Forex.EURUSD", "sanity:EURUSD", "MISSING",
                f"saneamiento cruzado: EURUSD×USDEUR={product:.4f}, no ~1",
            )
            rejected.append("EURUSD")
    return rejected


def _restamp_observation_quality(data: Dict[str, Any]) -> None:
    """as_of = fecha de la observación FRED, no la hora de captura NEXUS."""
    mapping = (
        ("CPI_YoY_Pct", "CPI_AsOf", "FRED:CPIAUCSL"),
        ("CPI_Latest", "CPI_AsOf", "FRED:CPIAUCSL"),
        ("M2_Change_Pct", "M2_AsOf", "FRED:WM2NS"),
        ("M2_Latest", "M2_AsOf", "FRED:WM2NS"),
        ("China_M2_YoY_Pct", "China_M2_AsOf", "FRED:MYAGM2CNM189N"),
        ("US2Y", "US2Y_AsOf", "FRED:DGS2"),
    )
    quality = data.setdefault("DataQuality", {})
    for key, as_of_key, _source in mapping:
        as_of = data.get(as_of_key)
        item = quality.get(key)
        if not as_of or not isinstance(item, dict):
            continue
        item["as_of"] = as_of
        detail = str(item.get("detail") or "")
        note = f"observación {as_of}"
        if note not in detail:
            item["detail"] = f"{detail}; {note}".strip("; ") if detail else note


def _fetch_fred_series(series_id: str, limit: int = 12) -> list | None:
    """
    Descarga una serie temporal de FRED (Federal Reserve Economic Data).

    Args:
        series_id: Identificador de la serie (ej. "M2SL", "CPIAUCSL").
        limit: Número de observaciones más recientes a devolver.

    Returns:
        Lista de dicts con 'date' y 'value', o None si falla.
    """
    if not FRED_API_KEY:
        return None

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "desc",
        "limit": limit,
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        observations = data.get("observations", [])
        return [
            {"date": obs["date"], "value": float(obs["value"])}
            for obs in observations
            if obs.get("value") not in (None, ".", "")
        ]
    except Exception as e:
        logging.warning(f"Error al obtener serie FRED '{series_id}': {e}")
        return None


def _fetch_sp500_pe_job(output_path: str) -> None:
    result = {"PE_Trailing": None, "PE_Forward": None}
    for ticker_sym in ["SPY", "IVV", "VOO"]:
        try:
            info = yf.Ticker(ticker_sym).info
            if result["PE_Trailing"] is None and info.get("trailingPE"):
                result["PE_Trailing"] = float(info["trailingPE"])
            if result["PE_Forward"] is None and info.get("forwardPE"):
                result["PE_Forward"] = float(info["forwardPE"])
            if result["PE_Trailing"] is not None and result["PE_Forward"] is not None:
                break
        except Exception as exc:
            logging.warning(f"Error al obtener PER de {ticker_sym}: {exc}")
    Path(output_path).write_text(json.dumps(result), encoding="utf-8")


def _fetch_sp500_pe() -> Dict[str, float | None]:
    """
    Obtiene el PER (trailing y forward) del S&P 500.

    Prueba SPY primero, y si falta algún dato, usa IVV o VOO como fallback
    (todos son ETFs que replican el S&P 500 de diferentes gestoras).
    yfinance.info no tiene timeout: se ejecuta en un proceso matable.
    """
    empty = {"PE_Trailing": None, "PE_Forward": None}
    handle = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
    output_path = handle.name
    handle.close()
    try:
        rc = _run_isolated(
            "from data_ingestion import _fetch_sp500_pe_job; "
            f"_fetch_sp500_pe_job({output_path!r})",
            timeout=12,
        )
        if rc != 0 or not Path(output_path).exists() or Path(output_path).stat().st_size == 0:
            if rc == -9:
                logging.warning("PER de yfinance superó 12s; se mantiene la caché local si existe.")
            return empty
        raw = json.loads(Path(output_path).read_text(encoding="utf-8"))
        return {
            "PE_Trailing": raw.get("PE_Trailing"),
            "PE_Forward": raw.get("PE_Forward"),
        }
    except Exception as exc:
        logging.warning(f"Fallo al obtener PER: {exc}")
        return empty
    finally:
        try:
            Path(output_path).unlink(missing_ok=True)
        except Exception:
            pass


def _fetch_siblis_forward_pe() -> Dict[str, Any]:
    """
    Obtiene PER forward desde Siblis Research Free API y calcula percentil histórico.
    """
    result = {
        "PE_Forward": None,
        "PE_Forward_Date": None,
        "PE_Forward_Source": None,
        "PE_Forward_Percentile": None,
    }
    url = "https://siblisresearch.supabase.co/functions/v1/free-data-api/v1/USA/pe-forward"

    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        payload = resp.json()
        rows = payload.get("data", [])
        valid_rows = [row for row in rows if row.get("value") is not None]
        if not valid_rows:
            return result

        latest = valid_rows[-1]
        values = [float(row["value"]) for row in valid_rows]
        current = float(latest["value"])
        rank = sum(1 for value in values if value <= current)
        percentile = round((rank / len(values)) * 100, 1)

        result["PE_Forward"] = current
        result["PE_Forward_Date"] = latest.get("trading_day (EOD)")
        result["PE_Forward_Source"] = "Siblis USA Large Cap proxy"
        result["PE_Forward_Percentile"] = percentile
    except Exception as e:
        logging.warning(f"Error al obtener PER forward desde Siblis: {e}")

    return result


def _fetch_latest_fred_value(series_id: str) -> float | None:
    observations = _fetch_fred_series(series_id, limit=5)
    if not observations:
        return None
    return observations[0]["value"]


# ─────────────────────────────────────────────────────────────
# Función principal
# ─────────────────────────────────────────────────────────────

def fetch_market_data(*, refresh: bool = False) -> Dict[str, Any]:
    """
    Descarga todos los datos del mercado disponibles.

    Con refresh=False (apertura de la app) se sirve la caché local si está
    completa, aunque esté caducada. Yahoo/FRED solo se consultan en Actualizar.

    Variables extraídas:
    - VIX: actual + medias móviles (5, 10, 20 días).
    - US10Y: rentabilidad bono a 10 años.
    - Correlación: media de 5 ETFs sectoriales.
    - PER: trailing y forward del S&P 500 (vía SPY).
    - M2: masa monetaria M2 de EE.UU. (vía FRED, opcional).
    - IPC: índice de precios al consumidor (vía FRED, opcional).
    - Assets: tendencia, momentum y volatilidad de SPY, QQQ, TLT, GLD y UUP.
    - Forex: métricas de EUR/USD (spot, tendencia, momentum y volatilidad).
    """
    cache = _load_market_cache()
    fast_cache = _load_tier_cache(FAST_MARKET_CACHE_FILE)
    slow_cache = _load_tier_cache(SLOW_MACRO_CACHE_FILE)
    rotation_cache = _load_tier_cache(ROTATION_MARKET_CACHE_FILE)
    use_fast_cache = _fast_cache_usable(fast_cache)
    use_slow_cache = _slow_cache_usable(slow_cache)
    use_rotation_cache = _rotation_cache_usable(rotation_cache)
    rotation_cache_updated = False
    captured_at = _now_utc_iso()
    data: Dict[str, Any] = {
        "VIX": None,
        "VIX_MA5": None,
        "VIX_MA10": None,
        "VIX_MA20": None,
        "US10Y": None,
        "Correlation_Proxy": None,
        "PE_Trailing": None,
        "PE_Forward": None,
        "PE_Forward_Date": None,
        "PE_Forward_Source": None,
        "PE_Forward_Percentile": None,
        "US2Y": None,
        "Yield_Curve_Spread": None,
        "China_M2_YoY_Pct": None,
        "M2_Latest": None,
        "M2_Previous": None,
        "M2_Change_Pct": None,
        "CPI_Latest": None,
        "CPI_YoY_Pct": None,
        "M2_AsOf": None,
        "CPI_AsOf": None,
        "China_M2_AsOf": None,
        "US2Y_AsOf": None,
        "CrossPrices": {},
        "DataQuality": {},
        "Assets": {
            ticker: {
                "price": None,
                "ma20": None,
                "ma50": None,
                "ma200": None,
                "momentum_1m": None,
                "momentum_3m": None,
                "volatility_20d": None,
            }
            for ticker in DECISION_ASSETS
        },
        "RotationAssets": {
            ticker: {
                "price": None,
                "ma20": None,
                "ma50": None,
                "ma200": None,
                "momentum_1m": None,
                "momentum_3m": None,
                "volatility_20d": None,
            }
            for ticker in ROTATION_ASSETS
        },
        "RotationCompanies": {
            ticker: {
                "price": None,
                "ma20": None,
                "ma50": None,
                "ma200": None,
                "momentum_1m": None,
                "momentum_3m": None,
                "volatility_20d": None,
            }
            for ticker in sorted(set(ROTATION_COMPANY_TICKERS.values()))
        },
        "Forex": {
            pair: {
                "price": None,
                "ma20": None,
                "ma50": None,
                "ma200": None,
                "momentum_1m": None,
                "momentum_3m": None,
                "volatility_20d": None,
            }
            for pair in FOREX_TICKERS
        },
        "GlobalMarkets": {
            region: {
                "price": None,
                "ma20": None,
                "ma50": None,
                "ma200": None,
                "momentum_1m": None,
                "momentum_3m": None,
                "volatility_20d": None,
            }
            for region in GLOBAL_MARKET_TICKERS
        },
        "PriceSparklines": {},
    }

    global_tickers = list(GLOBAL_MARKET_TICKERS.values())
    have_fast = _fast_cache_complete(fast_cache)
    have_rotation = _rotation_cache_complete(rotation_cache)
    have_slow = _slow_cache_complete(slow_cache)
    market_live = False

    # ─── 1. Datos de yfinance (VIX, US10Y, ETFs, PER) ───
    if have_fast:
        logging.info(
            "Usando cache de mercado (%s)...",
            "fresca" if use_fast_cache else "caducada",
        )
        _apply_tier_cache(data, fast_cache, FAST_CACHE_KEYS, stale=not use_fast_cache)

    should_download_market = refresh or not have_fast
    if should_download_market:
        tickers = sorted(set(
            ["^VIX", "^TNX", "IVV", "USDEUR=X"] + SECTOR_ETFS + DECISION_ASSETS + ROTATION_ASSETS
            + list(FOREX_TICKERS.values()) + global_tickers
        ))
        logging.info("Descargando datos de mercado (yfinance, 2 años)...")
        df = _yf_download(tickers)
        if df is not None and not df.empty and "Close" in df.columns:
            df_close = df["Close"]

            # VIX
            if "^VIX" in df_close.columns:
                vix_s = df_close["^VIX"].dropna()
                if not vix_s.empty:
                    data["VIX"] = float(vix_s.iloc[-1])
                    _mark_quality(data, "VIX", "yfinance:^VIX")
                    if len(vix_s) >= 5:
                        data["VIX_MA5"] = float(vix_s.tail(5).mean())
                        _mark_quality(data, "VIX_MA5", "yfinance:^VIX")
                    if len(vix_s) >= 10:
                        data["VIX_MA10"] = float(vix_s.tail(10).mean())
                        _mark_quality(data, "VIX_MA10", "yfinance:^VIX")
                    if len(vix_s) >= 20:
                        data["VIX_MA20"] = float(vix_s.tail(20).mean())
                        _mark_quality(data, "VIX_MA20", "yfinance:^VIX")

            # US10Y
            if "^TNX" in df_close.columns:
                tnx_s = df_close["^TNX"].dropna()
                if not tnx_s.empty:
                    data["US10Y"] = float(tnx_s.iloc[-1])
                    _mark_quality(data, "US10Y", "yfinance:^TNX")

            # Correlación sectorial
            data["Correlation_Proxy"] = _calculate_sector_correlation(df_close, SECTOR_ETFS)
            if data["Correlation_Proxy"] is not None:
                _mark_quality(data, "Correlation_Proxy", "yfinance:sector_etfs")

            # Métricas por activo para la decisión final
            data["Assets"] = {
                ticker: _calculate_asset_metrics(df_close, ticker)
                for ticker in DECISION_ASSETS
            }
            for ticker, metrics in data["Assets"].items():
                status = "OK" if metrics.get("price") is not None else "MISSING"
                _mark_quality(data, f"Assets.{ticker}", f"yfinance:{ticker}", status)

            data["RotationAssets"] = {
                ticker: _calculate_asset_metrics(df_close, ticker)
                for ticker in ROTATION_ASSETS
            }
            for ticker, metrics in data["RotationAssets"].items():
                status = "OK" if metrics.get("price") is not None else "MISSING"
                _mark_quality(data, f"RotationAssets.{ticker}", f"yfinance:{ticker}", status)

            data["Forex"] = {
                pair: _calculate_asset_metrics(df_close, ticker)
                for pair, ticker in FOREX_TICKERS.items()
            }
            for pair, ticker in FOREX_TICKERS.items():
                status = "OK" if data["Forex"].get(pair, {}).get("price") is not None else "MISSING"
                _mark_quality(data, f"Forex.{pair}", f"yfinance:{ticker}", status)

            data["GlobalMarkets"] = {
                region: _calculate_asset_metrics(df_close, ticker)
                for region, ticker in GLOBAL_MARKET_TICKERS.items()
            }
            for region, ticker in GLOBAL_MARKET_TICKERS.items():
                status = "OK" if data["GlobalMarkets"].get(region, {}).get("price") is not None else "MISSING"
                _mark_quality(data, f"GlobalMarkets.{region}", f"yfinance:{ticker}", status)

            sparklines = _build_sparklines(df_close)
            ohlc_charts = _build_ohlc_sparklines(df, df_close)
            if ohlc_charts:
                sparklines = {**(sparklines or {}), **ohlc_charts}
            if sparklines:
                data["PriceSparklines"] = {**(data.get("PriceSparklines") or {}), **sparklines}

            cross = {
                "IVV": _close_last(df_close, "IVV"),
                "USDEUR": _close_last(df_close, "USDEUR=X"),
            }
            data["CrossPrices"] = {key: value for key, value in cross.items() if value is not None}

            market_live = True
            logging.info("Datos de yfinance extraídos.")
        elif not _fast_cache_complete(fast_cache):
            for key in ["VIX", "US10Y", "Correlation_Proxy", "Assets", "Forex"]:
                _mark_quality(data, key, "yfinance", "ERROR", "sin respuesta a tiempo")

    # ─── 1b. Detalle de empresas de rotación (caché independiente) ───
    # Estas empresas alimentan la vista detallada, pero no deben bloquear ni
    # encarecer la actualización del snapshot principal.
    company_tickers = sorted(set(ROTATION_COMPANY_TICKERS.values()))
    if have_rotation:
        logging.info(
            "Usando cache de empresas de rotación (%s)...",
            "fresca" if use_rotation_cache else "caducada",
        )
        _apply_tier_cache(data, rotation_cache, ROTATION_CACHE_KEYS, stale=not use_rotation_cache)

    if refresh and company_tickers and not have_rotation:
        logging.info("Descargando detalle de empresas de rotación (yfinance, 2 años)...")
        company_df = _yf_download(company_tickers)
        if company_df is not None and not company_df.empty and "Close" in company_df.columns:
            company_close = company_df["Close"]
            data["RotationCompanies"] = {
                ticker: _calculate_asset_metrics(company_close, ticker)
                for ticker in company_tickers
            }
            for ticker, metrics in data["RotationCompanies"].items():
                status = "OK" if metrics.get("price") is not None else "MISSING"
                _mark_quality(data, f"RotationCompanies.{ticker}", f"yfinance:{ticker}", status)
            rotation_cache_updated = any(
                metrics.get("price") is not None
                for metrics in data["RotationCompanies"].values()
            )
            company_sparks = _build_sparklines(company_close, tickers=company_tickers)
            company_ohlc = _build_ohlc_sparklines(company_df, company_close, tickers=company_tickers)
            merged = {**(company_sparks or {}), **(company_ohlc or {})}
            if merged:
                data["PriceSparklines"] = {**(data.get("PriceSparklines") or {}), **merged}
        elif not _rotation_cache_complete(rotation_cache):
            _mark_quality(data, "RotationCompanies", "yfinance:companies", "MISSING", "sin respuesta a tiempo")

    # ─── 2. PER del S&P 500 / Large Cap USA ───
    if have_slow:
        logging.info(
            "Usando cache lenta de macro (%s)...",
            "fresca" if use_slow_cache else "caducada",
        )
        _apply_tier_cache(data, slow_cache, SLOW_CACHE_KEYS, stale=not use_slow_cache)

    # PER/FRED no cambian en cada auto-refresh. Si la caché macro sigue vigente,
    # no se vuelve a consultar: yfinance.info se queda colgado minutos.
    macro_live = not use_slow_cache and (refresh or not have_slow)
    if macro_live:
        try:
            logging.info("Obteniendo PER del S&P 500 (SPY)...")
            pe_data = _fetch_sp500_pe()
            data.update(pe_data)
            for key, value in pe_data.items():
                _mark_quality(data, key, "yfinance:SPY/IVV/VOO", "OK" if value is not None else "MISSING")
        except Exception as e:
            logging.warning(f"Fallo al obtener PER: {e}")
            _mark_quality(data, "PE_Trailing", "yfinance:SPY/IVV/VOO", "ERROR", str(e))
            _mark_quality(data, "PE_Forward", "yfinance:SPY/IVV/VOO", "ERROR", str(e))

        try:
            if data.get("PE_Forward") is None:
                logging.info("Obteniendo PER forward desde Siblis (USA Large Cap proxy)...")
                fwd_data = _fetch_siblis_forward_pe()
                if fwd_data.get("PE_Forward") is not None:
                    data.update(fwd_data)
                    _mark_quality(
                        data,
                        "PE_Forward",
                        "Siblis:USA/pe-forward",
                        "OK",
                        f"Proxy U.S. Large Cap; fecha EOD {fwd_data.get('PE_Forward_Date')}",
                    )
                    if fwd_data.get("PE_Forward_Percentile") is not None:
                        _mark_quality(data, "PE_Forward_Percentile", "Siblis:USA/pe-forward", "OK")
                else:
                    _mark_quality(data, "PE_Forward", "Siblis:USA/pe-forward", "MISSING")
        except Exception as e:
            logging.warning(f"Fallo al obtener PER forward alternativo: {e}")
            _mark_quality(data, "PE_Forward", "Siblis:USA/pe-forward", "ERROR", str(e))

        # ─── 2b. Tipos 2Y y curva de rendimiento ───
        if FRED_API_KEY:
            logging.info("Descargando tipos 2Y desde FRED...")
            us2y_obs = _fetch_fred_series("DGS2", limit=5)
            if us2y_obs:
                us2y = us2y_obs[0]["value"]
                data["US2Y"] = us2y
                data["US2Y_AsOf"] = us2y_obs[0]["date"]
                _mark_quality(data, "US2Y", "FRED:DGS2", as_of=data["US2Y_AsOf"])
                if data.get("US10Y") is not None:
                    data["Yield_Curve_Spread"] = round(data["US10Y"] - us2y, 2)
                    _mark_quality(data, "Yield_Curve_Spread", "FRED:DGS2+^TNX", as_of=data["US2Y_AsOf"])
            else:
                _mark_quality(data, "Yield_Curve_Spread", "FRED:DGS2", "MISSING")
        else:
            _mark_quality(data, "Yield_Curve_Spread", "FRED:DGS2", "MISSING", "FRED_API_KEY no configurada")

        # ─── 3. FRED: Masa Monetaria M2 (liquidez) ───
        if FRED_API_KEY:
            logging.info("Descargando M2 (liquidez) desde FRED...")
            m2_obs = _fetch_fred_series("WM2NS", limit=14)
            if m2_obs and len(m2_obs) >= 2:
                data["M2_Latest"] = m2_obs[0]["value"]
                data["M2_Previous"] = m2_obs[-1]["value"]
                data["M2_AsOf"] = m2_obs[0]["date"]
                _mark_quality(data, "M2_Latest", "FRED:WM2NS", as_of=data["M2_AsOf"])
                _mark_quality(data, "M2_Previous", "FRED:WM2NS", as_of=m2_obs[-1]["date"])
                if data["M2_Previous"] > 0:
                    data["M2_Change_Pct"] = round(
                        ((data["M2_Latest"] - data["M2_Previous"]) / data["M2_Previous"]) * 100, 2
                    )
                    _mark_quality(data, "M2_Change_Pct", "FRED:WM2NS", as_of=data["M2_AsOf"])
            else:
                _mark_quality(data, "M2_Change_Pct", "FRED:WM2NS", "MISSING")
        else:
            logging.info("FRED_API_KEY no configurada. M2 desactivado.")
            _mark_quality(data, "M2_Change_Pct", "FRED:WM2NS", "MISSING", "FRED_API_KEY no configurada")

        # ─── 4. FRED: IPC / Inflación ───
        if FRED_API_KEY:
            logging.info("Descargando IPC (inflación) desde FRED...")
            cpi_obs = _fetch_fred_series("CPIAUCSL", limit=24)
            if cpi_obs and len(cpi_obs) >= 2:
                data["CPI_Latest"] = cpi_obs[0]["value"]
                data["CPI_AsOf"] = cpi_obs[0]["date"]
                _mark_quality(data, "CPI_Latest", "FRED:CPIAUCSL", as_of=data["CPI_AsOf"])
                if len(cpi_obs) >= 13:
                    # Buscar por fecha: ~12 meses atrás en lugar de índice fijo
                    try:
                        latest_dt = datetime.strptime(cpi_obs[0]["date"], "%Y-%m-%d")
                        target_dt = latest_dt.replace(year=latest_dt.year - 1)
                        cpi_12m_ago = _find_obs_near_date(cpi_obs, target_dt.strftime("%Y-%m-%d"))
                    except (ValueError, KeyError):
                        cpi_12m_ago = cpi_obs[12]["value"]
                    if cpi_12m_ago is not None and cpi_12m_ago > 0:
                        data["CPI_YoY_Pct"] = round(
                            ((data["CPI_Latest"] - cpi_12m_ago) / cpi_12m_ago) * 100, 2
                        )
                        _mark_quality(data, "CPI_YoY_Pct", "FRED:CPIAUCSL", as_of=data.get("CPI_AsOf"))
            else:
                _mark_quality(data, "CPI_YoY_Pct", "FRED:CPIAUCSL", "MISSING")
        else:
            logging.info("FRED_API_KEY no configurada. IPC desactivado.")
            _mark_quality(data, "CPI_YoY_Pct", "FRED:CPIAUCSL", "MISSING", "FRED_API_KEY no configurada")

        # ─── 5. FRED: Liquidez China (M2 YoY) ───
        if FRED_API_KEY:
            logging.info("Descargando M2 China desde FRED...")
            china_obs = _fetch_fred_series("MYAGM2CNM189N", limit=24)
            if china_obs and len(china_obs) >= 13:
                latest = china_obs[0]["value"]
                # Buscar por fecha: ~12 meses atrás en lugar de índice fijo
                try:
                    latest_dt = datetime.strptime(china_obs[0]["date"], "%Y-%m-%d")
                    target_dt = latest_dt.replace(year=latest_dt.year - 1)
                    year_ago = _find_obs_near_date(china_obs, target_dt.strftime("%Y-%m-%d"))
                except (ValueError, KeyError):
                    year_ago = china_obs[12]["value"]
                if year_ago is not None and year_ago > 0:
                    data["China_M2_YoY_Pct"] = round(((latest - year_ago) / year_ago) * 100, 2)
                    data["China_M2_AsOf"] = china_obs[0]["date"]
                    _mark_quality(
                        data, "China_M2_YoY_Pct", "FRED:MYAGM2CNM189N", as_of=data["China_M2_AsOf"]
                    )
            else:
                _mark_quality(data, "China_M2_YoY_Pct", "FRED:MYAGM2CNM189N", "MISSING")
        else:
            _mark_quality(data, "China_M2_YoY_Pct", "FRED:MYAGM2CNM189N", "MISSING", "FRED_API_KEY no configurada")

    data = _apply_cache_fallback(data, cache)
    for key in [
        "VIX", "US10Y", "US2Y", "Yield_Curve_Spread", "Correlation_Proxy",
        "PE_Trailing", "PE_Forward", "PE_Forward_Percentile",
        "M2_Change_Pct", "CPI_YoY_Pct", "China_M2_YoY_Pct",
    ]:
        if key not in data["DataQuality"]:
            _mark_quality(data, key, "unknown", "MISSING")
    _restamp_observation_quality(data)
    sanity_rejected = _apply_cross_sanity(data)
    data["DataQuality"]["snapshot"] = _quality("NEXUS", "OK", captured_at, "snapshot de ejecución")
    macro_freshness = _layer_freshness(
        "Macro",
        slow_cache,
        live=macro_live,
        present=have_slow or macro_live,
        ttl=SLOW_MACRO_CACHE_TTL_SECONDS,
    )
    obs_as_of = data.get("CPI_AsOf") or data.get("M2_AsOf")
    if obs_as_of:
        macro_freshness["as_of"] = obs_as_of
    data["Freshness"] = {
        "market": _layer_freshness(
            "Mercado",
            fast_cache,
            live=market_live,
            present=have_fast or market_live,
            ttl=FAST_MARKET_CACHE_TTL_SECONDS,
        ),
        "macro": macro_freshness,
        "companies": _layer_freshness(
            "Empresas",
            rotation_cache,
            live=rotation_cache_updated,
            present=have_rotation or rotation_cache_updated,
            ttl=ROTATION_MARKET_CACHE_TTL_SECONDS,
        ),
    }

    core_sane = "VIX" not in sanity_rejected and "SPY" not in sanity_rejected
    if market_live and data.get("VIX") is not None and data.get("US10Y") is not None and core_sane:
        _save_market_cache(data)
        fast_payload = _extract_tier_payload(data, FAST_CACHE_KEYS)
        if fast_payload:
            _save_tier_cache(
                FAST_MARKET_CACHE_FILE, fast_payload,
                captured_at=captured_at, source="yfinance",
            )
    if macro_live:
        slow_payload = _extract_tier_payload(data, SLOW_CACHE_KEYS)
        if slow_payload:
            _save_tier_cache(
                SLOW_MACRO_CACHE_FILE, slow_payload,
                captured_at=captured_at, source="FRED",
            )

    # El detalle de empresas tiene ciclo de vida propio: puede guardarse aun
    # cuando una fuente macro concreta no haya respondido en este ciclo.
    rotation_payload = _extract_tier_payload(data, ROTATION_CACHE_KEYS)
    if rotation_cache_updated and rotation_payload:
        _save_tier_cache(
            ROTATION_MARKET_CACHE_FILE, rotation_payload,
            captured_at=captured_at, source="yfinance:companies",
        )

    logging.info("Ingesta de datos completada.")
    return data


if __name__ == "__main__":
    print("Obteniendo todos los datos macroeconómicos...\n")
    resultados = fetch_market_data()
    for key, value in resultados.items():
        if value is not None:
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: No disponible")
