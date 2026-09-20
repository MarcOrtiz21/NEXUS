"""Posicionamiento CFTC/COMEX del oro con contrato point-in-time.

La fuente es el informe público *Disaggregated Futures Only* de la CFTC. Los
datos se expresan en contratos de futuros COMEX Gold (100 onzas troy por
contrato) y porcentajes del interés abierto. La fecha del informe corresponde
al cierre del martes; ``release_at`` representa el instante en que el dato pudo
conocerse públicamente y es el único campo usado para los cortes históricos.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, time, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import pandas as pd
import requests
from pandas.tseries.holiday import USFederalHolidayCalendar
from pandas.tseries.offsets import CustomBusinessDay

from config import CFTC_GOLD_CACHE_FILE, CFTC_GOLD_CACHE_TTL_SECONDS


CFTC_DATASET_ID = "72hh-3qpy"
CFTC_GOLD_CONTRACT_CODE = "088691"
CFTC_SOURCE = "CFTC:COT Disaggregated Futures Only/COMEX 088691"
CFTC_API_URL = f"https://publicreporting.cftc.gov/resource/{CFTC_DATASET_ID}.json"

_FIELDS = (
    "report_date_as_yyyy_mm_dd",
    "market_and_exchange_names",
    "cftc_contract_market_code",
    "open_interest_all",
    "m_money_positions_long_all",
    "m_money_positions_short_all",
    "m_money_positions_spread",
    "change_in_m_money_long_all",
    "change_in_m_money_short_all",
    "pct_of_oi_m_money_long_all",
    "pct_of_oi_m_money_short_all",
    "pct_of_oi_m_money_spread",
    "conc_gross_le_4_tdr_long",
    "conc_gross_le_4_tdr_short",
    "conc_gross_le_8_tdr_long",
    "conc_gross_le_8_tdr_short",
    "contract_units",
)

# Publicaciones extraordinarias causadas por la interrupción de 2025. Sin
# estas excepciones, un backtest atribuiría datos al viernes originalmente
# previsto aunque la CFTC todavía no los hubiera publicado.
_RELEASE_OVERRIDES = {
    "2025-09-30": "2025-11-19",
    "2025-10-07": "2025-11-21",
    "2025-10-14": "2025-11-25",
    "2025-10-21": "2025-12-02",
    "2025-10-28": "2025-12-05",
    "2025-11-04": "2025-12-09",
    "2025-11-10": "2025-12-12",
    "2025-11-18": "2025-12-16",
    "2025-11-25": "2025-12-19",
    "2025-12-02": "2025-12-23",
    "2025-12-09": "2025-12-30",
    "2025-12-16": "2026-01-06",
    "2025-12-23": "2026-01-09",
    "2025-12-30": "2026-01-13",
    "2026-01-06": "2026-01-16",
    "2026-01-13": "2026-01-20",
    "2026-01-20": "2026-01-23",
}


def _number(value: Any) -> float | None:
    if value in (None, "", ".") or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(round(number)) if number is not None else None


def _report_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def release_at_for_report(report_date: date) -> datetime:
    """Devuelve la primera hora pública conservadora para un informe COT."""
    override = _RELEASE_OVERRIDES.get(report_date.isoformat())
    if override:
        release_date = date.fromisoformat(override)
    else:
        # La CFTC publica normalmente el tercer día hábil posterior al corte.
        release_date = (pd.Timestamp(report_date) + 3 * CustomBusinessDay(
            calendar=USFederalHolidayCalendar()
        )).date()
    eastern = ZoneInfo("America/New_York")
    return datetime.combine(release_date, time(15, 30), tzinfo=eastern).astimezone(timezone.utc)


def _parse_row(raw: dict[str, Any]) -> dict[str, Any] | None:
    report = _report_date(raw.get("report_date_as_yyyy_mm_dd"))
    if report is None or str(raw.get("cftc_contract_market_code") or "").strip() != CFTC_GOLD_CONTRACT_CODE:
        return None
    long_contracts = _integer(raw.get("m_money_positions_long_all"))
    short_contracts = _integer(raw.get("m_money_positions_short_all"))
    open_interest = _integer(raw.get("open_interest_all"))
    if long_contracts is None or short_contracts is None or not open_interest:
        return None
    net = long_contracts - short_contracts
    change_long = _integer(raw.get("change_in_m_money_long_all"))
    change_short = _integer(raw.get("change_in_m_money_short_all"))
    return {
        "report_date": report.isoformat(),
        "release_at": release_at_for_report(report).isoformat(timespec="seconds"),
        "market": str(raw.get("market_and_exchange_names") or "COMEX Gold").strip(),
        "contract_code": CFTC_GOLD_CONTRACT_CODE,
        "contract_units": str(raw.get("contract_units") or "CONTRACTS OF 100 TROY OUNCES").strip("() "),
        "open_interest_contracts": open_interest,
        "managed_money_long_contracts": long_contracts,
        "managed_money_short_contracts": short_contracts,
        "managed_money_spread_contracts": _integer(raw.get("m_money_positions_spread")),
        "managed_money_net_contracts": net,
        "managed_money_net_pct_oi": round(net / open_interest * 100, 4),
        "managed_money_long_pct_oi": _number(raw.get("pct_of_oi_m_money_long_all")),
        "managed_money_short_pct_oi": _number(raw.get("pct_of_oi_m_money_short_all")),
        "managed_money_spread_pct_oi": _number(raw.get("pct_of_oi_m_money_spread")),
        "weekly_net_change_contracts": (
            change_long - change_short
            if change_long is not None and change_short is not None else None
        ),
        "concentration_gross_4_long_pct": _number(raw.get("conc_gross_le_4_tdr_long")),
        "concentration_gross_4_short_pct": _number(raw.get("conc_gross_le_4_tdr_short")),
        "concentration_gross_8_long_pct": _number(raw.get("conc_gross_le_8_tdr_long")),
        "concentration_gross_8_short_pct": _number(raw.get("conc_gross_le_8_tdr_short")),
    }


def _derive(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda item: item["report_date"])
    for index, row in enumerate(ordered):
        net = float(row["managed_money_net_contracts"])
        net_pct = float(row["managed_money_net_pct_oi"])
        if index >= 4:
            prior = ordered[index - 4]
            row["four_week_net_change_contracts"] = int(
                net - float(prior["managed_money_net_contracts"])
            )
            row["four_week_net_change_pct_oi"] = round(
                net_pct - float(prior["managed_money_net_pct_oi"]), 4
            )
        else:
            row["four_week_net_change_contracts"] = None
            row["four_week_net_change_pct_oi"] = None

        history = [
            float(item["managed_money_net_pct_oi"])
            for item in ordered[max(0, index - 155): index + 1]
        ]
        if len(history) >= 26:
            less_or_equal = sum(value <= net_pct for value in history)
            row["net_percentile_3y"] = round(less_or_equal / len(history) * 100, 2)
            deviation = pstdev(history)
            row["net_zscore_3y"] = round((net_pct - mean(history)) / deviation, 3) if deviation else 0.0
        else:
            row["net_percentile_3y"] = None
            row["net_zscore_3y"] = None
    return ordered


def _cache_is_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age <= CFTC_GOLD_CACHE_TTL_SECONDS


def _read_cache(path: Path = CFTC_GOLD_CACHE_FILE) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("rows") if isinstance(payload, dict) else None
        return rows if isinstance(rows, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_cache(rows: list[dict[str, Any]], path: Path = CFTC_GOLD_CACHE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": CFTC_SOURCE,
        "dataset_id": CFTC_DATASET_ID,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": rows,
    }
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def fetch_gold_cot_history(
    *,
    refresh: bool = False,
    start: date | None = None,
    end: date | None = None,
    cache_path: Path = CFTC_GOLD_CACHE_FILE,
    session: Any = requests,
) -> list[dict[str, Any]]:
    """Descarga y cachea exclusivamente las filas COMEX Gold de la CFTC."""
    cached = _read_cache(cache_path)
    rows = cached
    if refresh or not cached or not _cache_is_fresh(cache_path):
        params = {
            "$select": ",".join(_FIELDS),
            "$where": f"cftc_contract_market_code='{CFTC_GOLD_CONTRACT_CODE}'",
            "$order": "report_date_as_yyyy_mm_dd ASC",
            "$limit": 5000,
        }
        try:
            response = session.get(CFTC_API_URL, params=params, timeout=20)
            response.raise_for_status()
            parsed = [item for raw in response.json() if (item := _parse_row(raw)) is not None]
            if parsed:
                rows = _derive(parsed)
                _write_cache(rows, cache_path)
        except Exception:
            # La aplicación debe seguir abriendo con la última caché; si nunca
            # hubo una, la ausencia se propaga explícitamente.
            rows = cached

    filtered = []
    for row in rows:
        report = _report_date(row.get("report_date"))
        if report is None:
            continue
        if start and report < start:
            continue
        if end and report > end:
            continue
        filtered.append(dict(row))
    return _derive(filtered) if filtered else []


def _as_utc(value: datetime | date | str | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.max)
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def known_cot_rows(rows: Iterable[dict[str, Any]], cutoff: datetime | date | str | None) -> list[dict[str, Any]]:
    limit = _as_utc(cutoff)
    known = []
    for row in rows:
        try:
            released = _as_utc(row.get("release_at"))
        except (TypeError, ValueError):
            continue
        if released <= limit:
            known.append(dict(row))
    return sorted(known, key=lambda item: item["report_date"])


def summarize_gold_positioning(
    rows: Iterable[dict[str, Any]],
    *,
    as_of: datetime | date | str | None = None,
    gold_momentum_1m: float | None = None,
    price_points: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Resume la última observación conocida y prepara una serie para la UI."""
    cutoff = _as_utc(as_of)
    known = known_cot_rows(rows, cutoff)
    if not known:
        return {
            "status": "MISSING",
            "source": CFTC_SOURCE,
            "contract_code": CFTC_GOLD_CONTRACT_CODE,
            "as_of": None,
            "release_at": None,
            "history": [],
        }
    latest = dict(known[-1])
    four_week = _number(latest.get("four_week_net_change_contracts"))
    divergence = "SIN CONFIRMACIÓN"
    divergence_score = 0.0
    if gold_momentum_1m is not None and four_week is not None:
        if gold_momentum_1m >= 2 and four_week < 0:
            divergence, divergence_score = "PRECIO SUBE · POSICIÓN CAE", -1.0
        elif gold_momentum_1m <= -2 and four_week > 0:
            divergence, divergence_score = "PRECIO CAE · POSICIÓN SUBE", 1.0
        else:
            divergence = "PRECIO Y POSICIÓN ALINEADOS"

    prices: list[tuple[str, float]] = []
    for point in price_points or []:
        day = str(point.get("date") or "")[:10]
        value = _number(point.get("close", point.get("value")))
        if day and value is not None:
            prices.append((day, value))
    prices.sort()

    history = []
    selected = known[-104:]
    base_price = None
    for row in selected:
        report_day = row["report_date"]
        available_prices = [value for day, value in prices if day <= report_day]
        price = available_prices[-1] if available_prices else None
        if base_price is None and price:
            base_price = price
        zscore = _number(row.get("net_zscore_3y"))
        history.append({
            "report_date": report_day,
            "release_at": row.get("release_at"),
            "net_contracts": row.get("managed_money_net_contracts"),
            "net_pct_oi": row.get("managed_money_net_pct_oi"),
            "percentile_3y": row.get("net_percentile_3y"),
            "positioning_index": round(100 + 20 * zscore, 2) if zscore is not None else None,
            "gold_price": round(price, 2) if price is not None else None,
            "gold_price_index": round(price / base_price * 100, 2) if price and base_price else None,
        })

    age_days = max(0, (cutoff.date() - date.fromisoformat(latest["report_date"])).days)
    return {
        "status": "STALE" if age_days > 14 else "OK",
        "source": CFTC_SOURCE,
        "contract_code": CFTC_GOLD_CONTRACT_CODE,
        "contract_units": latest.get("contract_units"),
        "as_of": latest.get("report_date"),
        "release_at": latest.get("release_at"),
        "age_days": age_days,
        "open_interest_contracts": latest.get("open_interest_contracts"),
        "long_contracts": latest.get("managed_money_long_contracts"),
        "short_contracts": latest.get("managed_money_short_contracts"),
        "net_contracts": latest.get("managed_money_net_contracts"),
        "net_pct_oi": latest.get("managed_money_net_pct_oi"),
        "weekly_change_contracts": latest.get("weekly_net_change_contracts"),
        "four_week_change_contracts": latest.get("four_week_net_change_contracts"),
        "four_week_change_pct_oi": latest.get("four_week_net_change_pct_oi"),
        "percentile_3y": latest.get("net_percentile_3y"),
        "zscore_3y": latest.get("net_zscore_3y"),
        "concentration_4_long_pct": latest.get("concentration_gross_4_long_pct"),
        "concentration_4_short_pct": latest.get("concentration_gross_4_short_pct"),
        "concentration_8_long_pct": latest.get("concentration_gross_8_long_pct"),
        "concentration_8_short_pct": latest.get("concentration_gross_8_short_pct"),
        "price_positioning_divergence": divergence,
        "divergence_score": divergence_score,
        "history": history,
    }


def positioning_data_fields(summary: dict[str, Any]) -> dict[str, Any]:
    """Traduce el resumen al contrato plano consumido por gold_outlook."""
    return {
        "GoldCFTC": summary,
        "CFTC_AsOf": summary.get("as_of"),
        "CFTC_ReleaseAt": summary.get("release_at"),
        "CFTC_MM_Net_Contracts": summary.get("net_contracts"),
        "CFTC_MM_Net_Pct_OI": summary.get("net_pct_oi"),
        "CFTC_MM_Weekly_Change_Contracts": summary.get("weekly_change_contracts"),
        "CFTC_MM_4W_Change_Contracts": summary.get("four_week_change_contracts"),
        "CFTC_MM_4W_Change_Pct_OI": summary.get("four_week_change_pct_oi"),
        "CFTC_MM_Percentile_3Y": summary.get("percentile_3y"),
        "CFTC_MM_ZScore_3Y": summary.get("zscore_3y"),
        "CFTC_Price_Positioning_Divergence": summary.get("divergence_score"),
        "CFTC_Concentration_4_Long_Pct": summary.get("concentration_4_long_pct"),
        "CFTC_Concentration_4_Short_Pct": summary.get("concentration_4_short_pct"),
        "CFTC_Concentration_8_Long_Pct": summary.get("concentration_8_long_pct"),
        "CFTC_Concentration_8_Short_Pct": summary.get("concentration_8_short_pct"),
    }
