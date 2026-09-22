"""Demanda oficial de oro y presión de mercado ETF sin doble conteo.

Las reservas oficiales son contexto descriptivo y proceden únicamente de
fuentes públicas. El bloque ETF usa precio y volumen negociado de GLD: no es
un flujo de participaciones ni una variación de toneladas en custodia y nunca
se presenta como tal.
"""

from __future__ import annotations

import csv
import html
import io
import json
import math
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import requests

from config import GOLD_DEMAND_CACHE_FILE, GOLD_DEMAND_CACHE_TTL_SECONDS


TROY_OUNCE_GRAMS = 31.1034768
ECB_SOURCE = "ECB Data Portal: Reserve assets, monetary gold, volume"
ECB_URL = (
    "https://data-api.ecb.europa.eu/service/data/RAS/"
    "M.N.4F.W1.S121.S1.LE.A.FA.R.F11._Z.XGO.XAU._Z.N.ALL"
    "?lastNObservations=24&detail=dataonly"
)
ECB_PAGE = (
    "https://data.ecb.europa.eu/data/datasets/RAS/"
    "RAS.M.N.4F.W1.S121.S1.LE.A.FA.R.F11._Z.XGO.XAU._Z.N.ALL"
)
US_TREASURY_SOURCE = "U.S. Treasury: U.S. International Reserve Position"
US_TREASURY_INDEX = "https://home.treasury.gov/data/us-international-reserve-position"


def _number(value: Any) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "").strip())
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def _tonnes(million_fine_ounces: float) -> float:
    return round(million_fine_ounces * TROY_OUNCE_GRAMS, 3)


def parse_ecb_gold_csv(text: str) -> list[dict[str, Any]]:
    """Normaliza el CSV SDMX del BCE a observaciones mensuales en toneladas."""
    rows: list[dict[str, Any]] = []
    for raw in csv.DictReader(io.StringIO(text)):
        period = str(raw.get("TIME_PERIOD") or "").strip()
        value = _number(raw.get("OBS_VALUE"))
        if not re.fullmatch(r"\d{4}-\d{2}", period) or value is None:
            continue
        rows.append({
            "period": period,
            "million_fine_troy_ounces": round(value, 6),
            "tonnes": _tonnes(value),
            "status": str(raw.get("OBS_STATUS") or "").strip() or None,
            # Política conservadora: el dato mensual no se considera conocido
            # antes del día 15 del mes siguiente.
            "release_policy": "día 15 del mes siguiente (conservador)",
        })
    return sorted(rows, key=lambda item: item["period"])


def parse_us_treasury_links(text: str) -> list[str]:
    links = re.findall(
        r"(?:https://home\.treasury\.gov)?(/data/us-international-reserve-position/(\d{8}))",
        text,
        flags=re.IGNORECASE,
    )
    unique: dict[str, str] = {}
    for path, stamp in links:
        try:
            report = datetime.strptime(stamp, "%m%d%Y").date()
        except ValueError:
            continue
        unique[report.isoformat()] = f"https://home.treasury.gov{path.rstrip('/')}"
    return [unique[key] for key in sorted(unique, reverse=True)]


def parse_us_treasury_gold_page(text: str, url: str = "") -> dict[str, Any] | None:
    """Extrae fecha y volumen de oro del cuadro oficial del Tesoro."""
    plain = html.unescape(re.sub(r"<[^>]+>", " ", text))
    plain = re.sub(r"\s+", " ", plain)
    match = re.search(
        r"volume in millions of fine troy ounces.{0,220}?([0-9][0-9,]*\.?[0-9]*)",
        plain,
        flags=re.IGNORECASE,
    )
    volume = _number(match.group(1)) if match else None
    stamp = re.search(r"/([0-9]{8})(?:/)?$", url)
    if volume is None or stamp is None:
        return None
    try:
        report = datetime.strptime(stamp.group(1), "%m%d%Y").date()
    except ValueError:
        return None
    return {
        "period": report.isoformat(),
        "million_fine_troy_ounces": round(volume, 6),
        "tonnes": _tonnes(volume),
        "url": url,
    }


def _cache_fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now(timezone.utc).timestamp() - path.stat().st_mtime
    return age <= GOLD_DEMAND_CACHE_TTL_SECONDS


def _read_cache(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_cache(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def _reserve_record(
    identifier: str,
    label: str,
    source: str,
    source_url: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    latest = rows[-1] if rows else None
    previous = rows[-2] if len(rows) >= 2 else None
    change = None
    if latest and previous:
        change = round(float(latest["tonnes"]) - float(previous["tonnes"]), 3)
    return {
        "id": identifier,
        "label": label,
        "status": "OK" if latest else "MISSING",
        "as_of": latest.get("period") if latest else None,
        "tonnes": latest.get("tonnes") if latest else None,
        "change_tonnes": change,
        "previous_as_of": previous.get("period") if previous else None,
        "source": source,
        "source_url": source_url,
        "note": (
            "Saldo oficial publicado; una variación mide cambio de existencias, no compras intrames."
            if latest else "Fuente no disponible en esta actualización."
        ),
    }


def fetch_official_gold_demand(
    *,
    refresh: bool = False,
    cache_path: Path = GOLD_DEMAND_CACHE_FILE,
    session: Any = requests,
) -> dict[str, Any]:
    """Recupera BCE y Tesoro de EE. UU.; ante fallo conserva la última caché."""
    cached = _read_cache(cache_path)
    if cached and not refresh and _cache_fresh(cache_path):
        return cached

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    cached_records = {
        str(item.get("id")): item
        for item in ((cached or {}).get("reserves") or [])
        if isinstance(item, dict) and item.get("id")
    }

    def degraded_record(identifier: str, label: str, source: str, source_url: str) -> dict[str, Any]:
        previous = cached_records.get(identifier)
        if previous:
            record = dict(previous)
            record["status"] = "STALE"
            record["note"] = "Se muestra la última observación cacheada; la fuente no respondió."
            return record
        return _reserve_record(identifier, label, source, source_url, [])
    try:
        response = session.get(ECB_URL, headers={"Accept": "text/csv"}, timeout=20)
        response.raise_for_status()
        ecb_rows = parse_ecb_gold_csv(response.text)
        records.append(_reserve_record("ecb", "BCE", ECB_SOURCE, ECB_PAGE, ecb_rows))
    except Exception as exc:
        errors.append(f"BCE: {type(exc).__name__}")
        records.append(degraded_record("ecb", "BCE", ECB_SOURCE, ECB_PAGE))

    try:
        index = session.get(US_TREASURY_INDEX, timeout=20)
        index.raise_for_status()
        links = parse_us_treasury_links(index.text)
        # Último corte y referencia de aproximadamente un mes: evita cinco
        # peticiones semanales y sigue mostrando si el saldo cambió.
        selected = [links[0]] if links else []
        if len(links) > 4:
            selected.append(links[4])
        elif len(links) > 1:
            selected.append(links[-1])
        us_rows = []
        for link in reversed(selected):
            page = session.get(link, timeout=20)
            page.raise_for_status()
            parsed = parse_us_treasury_gold_page(page.text, link)
            if parsed:
                us_rows.append(parsed)
        records.append(_reserve_record(
            "us_treasury", "Tesoro de EE. UU.", US_TREASURY_SOURCE,
            US_TREASURY_INDEX, us_rows,
        ))
    except Exception as exc:
        errors.append(f"Tesoro EE. UU.: {type(exc).__name__}")
        records.append(degraded_record(
            "us_treasury", "Tesoro de EE. UU.", US_TREASURY_SOURCE, US_TREASURY_INDEX,
        ))

    if not records and cached:
        fallback = dict(cached)
        fallback["status"] = "STALE"
        fallback["errors"] = errors
        return fallback

    available = sum(item.get("status") in {"OK", "STALE"} for item in records)
    payload = {
        "status": "PARTIAL" if available else "MISSING",
        "coverage": {
            "available": available,
            "tracked": len(records),
            "scope": "BCE y Tesoro de EE. UU.; no representa la demanda oficial mundial",
        },
        "reserves": records,
        "score_enabled": False,
        "captured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "errors": errors,
    }
    if available and not errors:
        _write_cache(payload, cache_path)
    return payload


def build_etf_market_proxy(points: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Resume presión negociada de GLD sin confundirla con flujos del fondo."""
    usable = []
    for point in points or []:
        close = _number(point.get("value"))
        volume = _number(point.get("volume"))
        if close is not None and close > 0 and volume is not None and volume >= 0:
            usable.append((str(point.get("date") or ""), close, volume))
    if len(usable) < 21:
        return {
            "status": "MISSING",
            "instrument": "GLD",
            "score_enabled": False,
            "method": "volumen direccional de mercado",
            "note": "No hay 21 sesiones con volumen; no se infiere un flujo ETF.",
        }

    window = usable[-21:]
    signed_volume = 0.0
    total_volume = 0.0
    for previous, current in zip(window, window[1:]):
        delta = current[1] - previous[1]
        direction = 1.0 if delta > 0 else -1.0 if delta < 0 else 0.0
        signed_volume += direction * current[2]
        total_volume += current[2]
    pressure = signed_volume / total_volume if total_volume else None
    recent_volume = sum(item[2] for item in usable[-5:]) / 5
    baseline_volume = sum(item[2] for item in usable[-20:]) / 20
    price_return = (usable[-1][1] / usable[-21][1] - 1) * 100
    label = "NEUTRAL"
    if pressure is not None and pressure >= 0.15:
        label = "PRESIÓN COMPRADORA"
    elif pressure is not None and pressure <= -0.15:
        label = "PRESIÓN VENDEDORA"
    return {
        "status": "PROXY",
        "instrument": "GLD",
        "label": label,
        "as_of": usable[-1][0] or None,
        "signed_volume_balance": round(pressure, 4) if pressure is not None else None,
        "price_return_1m_pct": round(price_return, 2),
        "volume_ratio_5d_20d": round(recent_volume / baseline_volume, 3) if baseline_volume else None,
        "score_enabled": False,
        "method": "balance de volumen direccional de 20 sesiones",
        "note": "Proxy de presión negociada; no mide entradas, salidas, participaciones ni toneladas del ETF.",
    }


def build_gold_demand(
    official: dict[str, Any] | None,
    gld_points: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    return {
        "status": (official or {}).get("status") or "MISSING",
        "official": official or {"status": "MISSING", "reserves": [], "score_enabled": False},
        "etf_market_proxy": build_etf_market_proxy(gld_points),
        "actual_etf_flows_status": "STANDBY",
        "score_enabled": False,
        "methodology": "Contexto separado del score hasta ampliar cobertura y validar valor incremental.",
    }
