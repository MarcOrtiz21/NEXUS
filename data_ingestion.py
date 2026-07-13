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
import sys
from datetime import datetime, timezone
from typing import Dict, Any
from itertools import combinations

from config import (
    FRED_API_KEY,
    MARKET_CACHE_FILE,
    MARKET_CACHE_MAX_AGE_SECONDS,
    FAST_MARKET_CACHE_FILE,
    SLOW_MACRO_CACHE_FILE,
    FAST_MARKET_CACHE_TTL_SECONDS,
    SLOW_MACRO_CACHE_TTL_SECONDS,
    GLOBAL_MARKET_TICKERS,
    PE_PERCENTILE_HIGH,
    PE_PERCENTILE_LOW,
)

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
ROTATION_ASSETS = ["AIQ", "SMH", "XLK", "XBI", "XLV", "KIE", "PJP"]

# Par principal de divisas para bloque FX.
FOREX_TICKERS = {"EURUSD": "EURUSD=X"}

FAST_CACHE_KEYS = (
    "VIX", "VIX_MA5", "VIX_MA10", "VIX_MA20", "US10Y", "Correlation_Proxy",
    "Assets", "RotationAssets", "Forex", "GlobalMarkets",
)

SLOW_CACHE_KEYS = (
    "US2Y", "Yield_Curve_Spread", "M2_Latest", "M2_Previous", "M2_Change_Pct",
    "CPI_Latest", "CPI_YoY_Pct", "China_M2_YoY_Pct",
    "PE_Trailing", "PE_Forward", "PE_Forward_Date", "PE_Forward_Source", "PE_Forward_Percentile",
)


# ─────────────────────────────────────────────────────────────
# Funciones auxiliares
# ─────────────────────────────────────────────────────────────

def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _quality(source: str, status: str = "OK", captured_at: str | None = None, detail: str = "") -> Dict[str, str]:
    return {
        "source": source,
        "status": status,
        "captured_at": captured_at or _now_utc_iso(),
        "detail": detail,
    }


def _mark_quality(data: Dict[str, Any], key: str, source: str, status: str = "OK", detail: str = "") -> None:
    data.setdefault("DataQuality", {})[key] = _quality(source, status, detail=detail)


def _load_market_cache() -> Dict[str, Any] | None:
    if not MARKET_CACHE_FILE.exists():
        return None
    try:
        age = datetime.now(timezone.utc).timestamp() - MARKET_CACHE_FILE.stat().st_mtime
        payload = json.loads(MARKET_CACHE_FILE.read_text(encoding="utf-8"))
        payload["_cache_age_seconds"] = age
        return payload
    except Exception as e:
        logging.warning(f"No se pudo leer cache de mercado: {e}")
        return None


def _save_market_cache(data: Dict[str, Any]) -> None:
    try:
        MARKET_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        MARKET_CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logging.warning(f"No se pudo guardar cache de mercado: {e}")


def _apply_cache_fallback(data: Dict[str, Any], cache: Dict[str, Any] | None) -> Dict[str, Any]:
    if not cache:
        return data

    cache_age = cache.get("_cache_age_seconds")
    stale = cache_age is None or cache_age > MARKET_CACHE_MAX_AGE_SECONDS
    for key, value in cache.items():
        if key.startswith("_") or key == "DataQuality":
            continue
        should_fallback = data.get(key) in (None, {})
        if key in ("Assets", "RotationAssets", "Forex"):
            should_fallback = not any(
                metrics.get("price") is not None
                for metrics in data.get(key, {}).values()
            )
        if should_fallback and value not in (None, {}):
            data[key] = value
            status = "STALE" if stale else "OK"
            _mark_quality(data, key, "cache", status, "fallback desde cache local")

    return data


def _load_tier_cache(path) -> Dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["_cache_age_seconds"] = age
        return payload
    except Exception as exc:
        logging.warning(f"No se pudo leer cache {path.name}: {exc}")
        return None


def _save_tier_cache(path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        clean = {k: v for k, v in payload.items() if not k.startswith("_")}
        path.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
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
        data[key] = value
        status = "STALE" if stale else "OK"
        _mark_quality(data, key, "cache", status, f"desde cache ({'stale' if stale else 'fresh'})")


def _extract_tier_payload(data: Dict[str, Any], keys: tuple[str, ...]) -> Dict[str, Any]:
    return {key: data.get(key) for key in keys if data.get(key) not in (None, {})}


def _fast_cache_usable(cache: Dict[str, Any] | None) -> bool:
    if not _cache_is_fresh(cache, FAST_MARKET_CACHE_TTL_SECONDS):
        return False
    assets = (cache or {}).get("Assets", {})
    return cache.get("VIX") is not None and assets.get("SPY", {}).get("price") is not None


def _slow_cache_usable(cache: Dict[str, Any] | None) -> bool:
    if not _cache_is_fresh(cache, SLOW_MACRO_CACHE_TTL_SECONDS):
        return False
    return any((cache or {}).get(key) is not None for key in SLOW_CACHE_KEYS)


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


def _fetch_sp500_pe() -> Dict[str, float | None]:
    """
    Obtiene el PER (trailing y forward) del S&P 500.

    Prueba SPY primero, y si falta algún dato, usa IVV o VOO como fallback
    (todos son ETFs que replican el S&P 500 de diferentes gestoras).
    """
    result = {"PE_Trailing": None, "PE_Forward": None}
    # Intentamos con varios ETFs del S&P 500 por si uno no expone el dato
    for ticker_sym in ["SPY", "IVV", "VOO"]:
        try:
            info = yf.Ticker(ticker_sym).info
            if result["PE_Trailing"] is None and info.get("trailingPE"):
                result["PE_Trailing"] = float(info["trailingPE"])
            if result["PE_Forward"] is None and info.get("forwardPE"):
                result["PE_Forward"] = float(info["forwardPE"])
            # Si ya tenemos ambos, no necesitamos más fallbacks
            if result["PE_Trailing"] is not None and result["PE_Forward"] is not None:
                break
        except Exception as e:
            logging.warning(f"Error al obtener PER de {ticker_sym}: {e}")
    return result


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

def fetch_market_data() -> Dict[str, Any]:
    """
    Descarga todos los datos del mercado disponibles.

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
    use_fast_cache = _fast_cache_usable(fast_cache)
    use_slow_cache = _slow_cache_usable(slow_cache)
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
    }

    global_tickers = list(GLOBAL_MARKET_TICKERS.values())
    # ─── 1. Datos de yfinance (VIX, US10Y, ETFs, PER) ───
    if use_fast_cache:
        logging.info("Usando cache rápida de mercado (precios/VIX)...")
        _apply_tier_cache(data, fast_cache, FAST_CACHE_KEYS, stale=False)
    else:
        tickers = sorted(
            set(["^VIX", "^TNX"] + SECTOR_ETFS + DECISION_ASSETS + ROTATION_ASSETS + list(FOREX_TICKERS.values()) + global_tickers)
        )
        try:
            logging.info("Descargando datos de mercado (yfinance, 1 año)...")
            df = yf.download(tickers, period="1y", progress=False)

            if not df.empty and "Close" in df.columns:
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

            logging.info("Datos de yfinance extraídos.")
        except Exception as e:
            logging.error(f"Fallo en yfinance: {e}")
            for key in ["VIX", "US10Y", "Correlation_Proxy", "Assets", "Forex"]:
                _mark_quality(data, key, "yfinance", "ERROR", str(e))

    # ─── 2. PER del S&P 500 / Large Cap USA ───
    if use_slow_cache:
        logging.info("Usando cache lenta de macro (FRED/PER)...")
        _apply_tier_cache(data, slow_cache, SLOW_CACHE_KEYS, stale=False)
    else:
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
            us2y = _fetch_latest_fred_value("DGS2")
            if us2y is not None:
                data["US2Y"] = us2y
                _mark_quality(data, "US2Y", "FRED:DGS2")
                if data.get("US10Y") is not None:
                    data["Yield_Curve_Spread"] = round(data["US10Y"] - us2y, 2)
                    _mark_quality(data, "Yield_Curve_Spread", "FRED:DGS2+^TNX")
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
                _mark_quality(data, "M2_Latest", "FRED:WM2NS")
                _mark_quality(data, "M2_Previous", "FRED:WM2NS")
                if data["M2_Previous"] > 0:
                    data["M2_Change_Pct"] = round(
                        ((data["M2_Latest"] - data["M2_Previous"]) / data["M2_Previous"]) * 100, 2
                    )
                    _mark_quality(data, "M2_Change_Pct", "FRED:WM2NS")
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
                _mark_quality(data, "CPI_Latest", "FRED:CPIAUCSL")
                if len(cpi_obs) >= 13:
                    cpi_12m_ago = cpi_obs[12]["value"]
                    if cpi_12m_ago > 0:
                        data["CPI_YoY_Pct"] = round(
                            ((data["CPI_Latest"] - cpi_12m_ago) / cpi_12m_ago) * 100, 2
                        )
                        _mark_quality(data, "CPI_YoY_Pct", "FRED:CPIAUCSL")
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
                year_ago = china_obs[12]["value"]
                if year_ago > 0:
                    data["China_M2_YoY_Pct"] = round(((latest - year_ago) / year_ago) * 100, 2)
                    _mark_quality(data, "China_M2_YoY_Pct", "FRED:MYAGM2CNM189N")
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
    data["DataQuality"]["snapshot"] = _quality("NEXUS", "OK", captured_at, "snapshot de ejecución")

    if data.get("VIX") is not None and data.get("US10Y") is not None:
        _save_market_cache(data)
        fast_payload = _extract_tier_payload(data, FAST_CACHE_KEYS)
        if fast_payload:
            _save_tier_cache(FAST_MARKET_CACHE_FILE, fast_payload)
        slow_payload = _extract_tier_payload(data, SLOW_CACHE_KEYS)
        if slow_payload:
            _save_tier_cache(SLOW_MACRO_CACHE_FILE, slow_payload)

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
