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
from typing import Dict, Any
from itertools import combinations

from config import FRED_API_KEY

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ETFs sectoriales para correlación media (10 pares posibles).
SECTOR_ETFS = ["XLK", "XLF", "XLV", "XLE", "XLP"]


# ─────────────────────────────────────────────────────────────
# Funciones auxiliares
# ─────────────────────────────────────────────────────────────

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
    """
    data: Dict[str, Any] = {
        "VIX": None,
        "VIX_MA5": None,
        "VIX_MA10": None,
        "VIX_MA20": None,
        "US10Y": None,
        "Correlation_Proxy": None,
        "PE_Trailing": None,
        "PE_Forward": None,
        "M2_Latest": None,
        "M2_Previous": None,
        "M2_Change_Pct": None,
        "CPI_Latest": None,
        "CPI_YoY_Pct": None,
    }

    # ─── 1. Datos de yfinance (VIX, US10Y, ETFs, PER) ───
    tickers = ["^VIX", "^TNX"] + SECTOR_ETFS
    try:
        logging.info("Descargando datos de mercado (yfinance, 3 meses)...")
        df = yf.download(tickers, period="3mo", progress=False)

        if not df.empty and "Close" in df.columns:
            df_close = df["Close"]

            # VIX
            if "^VIX" in df_close.columns:
                vix_s = df_close["^VIX"].dropna()
                if not vix_s.empty:
                    data["VIX"] = float(vix_s.iloc[-1])
                    if len(vix_s) >= 5:
                        data["VIX_MA5"] = float(vix_s.tail(5).mean())
                    if len(vix_s) >= 10:
                        data["VIX_MA10"] = float(vix_s.tail(10).mean())
                    if len(vix_s) >= 20:
                        data["VIX_MA20"] = float(vix_s.tail(20).mean())

            # US10Y
            if "^TNX" in df_close.columns:
                tnx_s = df_close["^TNX"].dropna()
                if not tnx_s.empty:
                    data["US10Y"] = float(tnx_s.iloc[-1])

            # Correlación sectorial
            data["Correlation_Proxy"] = _calculate_sector_correlation(df_close, SECTOR_ETFS)

        logging.info("Datos de yfinance extraídos.")
    except Exception as e:
        logging.error(f"Fallo en yfinance: {e}")

    # ─── 2. PER del S&P 500 (vía SPY) ───
    try:
        logging.info("Obteniendo PER del S&P 500 (SPY)...")
        pe_data = _fetch_sp500_pe()
        data.update(pe_data)
    except Exception as e:
        logging.warning(f"Fallo al obtener PER: {e}")

    # ─── 3. FRED: Masa Monetaria M2 (liquidez) ───
    if FRED_API_KEY:
        logging.info("Descargando M2 (liquidez) desde FRED...")
        m2_obs = _fetch_fred_series("WM2NS", limit=14)  # Semanal, últimas 14 semanas
        if m2_obs and len(m2_obs) >= 2:
            data["M2_Latest"] = m2_obs[0]["value"]
            data["M2_Previous"] = m2_obs[-1]["value"]
            if data["M2_Previous"] > 0:
                data["M2_Change_Pct"] = round(
                    ((data["M2_Latest"] - data["M2_Previous"]) / data["M2_Previous"]) * 100, 2
                )
    else:
        logging.info("FRED_API_KEY no configurada. M2 desactivado.")

    # ─── 4. FRED: IPC / Inflación ───
    if FRED_API_KEY:
        logging.info("Descargando IPC (inflación) desde FRED...")
        cpi_obs = _fetch_fred_series("CPIAUCSL", limit=24)  # Mensual, margen para descartar nulos
        if cpi_obs and len(cpi_obs) >= 2:
            data["CPI_Latest"] = cpi_obs[0]["value"]
            # Inflación interanual: comparar último dato con el de hace 12 meses
            if len(cpi_obs) >= 13:
                cpi_12m_ago = cpi_obs[12]["value"]
                if cpi_12m_ago > 0:
                    data["CPI_YoY_Pct"] = round(
                        ((data["CPI_Latest"] - cpi_12m_ago) / cpi_12m_ago) * 100, 2
                    )
    else:
        logging.info("FRED_API_KEY no configurada. IPC desactivado.")

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
