"""Demanda oficial de oro y presión de mercado ETF sin doble conteo.

Las reservas oficiales son contexto descriptivo y proceden únicamente de
fuentes públicas. El bloque ETF usa precio y volumen negociado de GLD: no es
un flujo de participaciones ni una variación de toneladas en custodia y nunca
se presenta como tal.
"""

from __future__ import annotations

import csv
import calendar
import html
import io
import json
import math
import re
from datetime import date, datetime, timezone
from html.parser import HTMLParser
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
SAFE_SOURCE = "SAFE: Official Reserve Assets, volumen de oro monetario"
SAFE_INDEX_CURRENT = "https://www.safe.gov.cn/en/2021/0203/2045.html"
SAFE_INDEX_PREVIOUS = "https://www.safe.gov.cn/en/2021/0203/2385.html"
RBI_BULLETIN_INDEX = "https://www.rbi.org.in/Scripts/BS_ViewBulletin.aspx"
RBI_SOURCE = "RBI Bulletin: Foreign Exchange Reserves, volumen físico"
RESERVE_SCHEMA_VERSION = 4
RESERVE_SCOPES = {
    "ecb": ("economic_area", "euro_area"),
    "us_treasury": ("country", "US"),
    "safe": ("country", "CN"),
    "rbi": ("country", "IN"),
    "nbp": ("country", "PL"),
}


class _SafeTable(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self.row: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append(re.sub(r"\s+", "", "".join(self.cell)))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


class _RbiRows(HTMLParser):
    """Filas de la tabla RBI, conservando colspan de las cabeceras anuales."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[tuple[str, int]]] = []
        self.row: list[tuple[str, int]] | None = None
        self.cell: list[str] | None = None
        self.span = 1

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = []
            self.span = int(dict(attrs).get("colspan") or 1)

    def handle_data(self, data: str) -> None:
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self.cell is not None and self.row is not None:
            self.row.append((re.sub(r"\s+", " ", "".join(self.cell)).strip(), self.span))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def parse_rbi_bulletin_html_links(index_html: str) -> list[str]:
    """Descubre solo páginas HTML oficiales de la tabla 33, nunca PDF o XLS."""
    links: list[str] = []
    for row in re.findall(r"<tr\b[^>]*>.*?</tr>", index_html, flags=re.I | re.S):
        if not re.search(r"33\.\s*Foreign Exchange Reserves", row, re.I):
            continue
        for identifier in re.findall(r"BS_ViewBulletin\.aspx\?Id=(\d+)", row, flags=re.I):
            url = f"{RBI_BULLETIN_INDEX}?Id={identifier}"
            if url not in links:
                links.append(url)
    return links


def rbi_previous_bulletin_url(index_html: str) -> str | None:
    """Deriva el archivo anterior solo de la edición identificada por RBI."""
    match = re.search(r"Reserve Bank of India Bulletin\s*-\s*([A-Za-z]+)\s+(20\d{2})", index_html)
    if not match:
        return None
    try:
        month = list(calendar.month_name).index(match.group(1))
    except ValueError:
        return None
    year = int(match.group(2))
    if month == 1:
        month, year = 12, year - 1
    else:
        month -= 1
    return f"{RBI_BULLETIN_INDEX}?mon={month}&yr={year}"


def parse_rbi_gold_html(text: str, source_url: str) -> list[dict[str, Any]]:
    """Extrae la fila de toneladas de oro de una edición HTML identificable.

    La cabecera de año y la fecha semanal deben casar con cada cantidad. La
    fecha del boletín se guarda como fecha, nunca como hora de publicación.
    """
    if not re.fullmatch(re.escape(RBI_BULLETIN_INDEX) + r"\?Id=\d+", source_url):
        return []
    marker = re.search(r"Volume\s*\(Metric Tonnes\)", text, flags=re.I)
    if not marker:
        return []
    start = text.rfind("<table", 0, marker.start())
    end = text.find("</table>", marker.end())
    if start < 0 or end < 0:
        return []
    heading = text.rfind("33. Foreign Exchange Reserves", 0, start)
    if heading < 0 or start - heading > 10_000:
        return []
    preamble = html.unescape(re.sub(r"<[^>]+>", " ", text[heading:start]))
    stamp = re.search(r"Date\s*:\s*([A-Za-z]+\s+\d{1,2},\s*\d{4})", preamble, flags=re.I)
    if not stamp:
        return []
    try:
        parts = re.fullmatch(r"([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", stamp.group(1))
        if parts is None:
            return []
        release_date = datetime.strptime(
            f"{parts.group(1)[:3]} {parts.group(2)}, {parts.group(3)}", "%b %d, %Y"
        ).date()
    except ValueError:
        return []
    parser = _RbiRows()
    parser.feed(text[start:end + len("</table>")])
    rows = parser.rows
    year_row = next((row for row in rows if len(row) >= 3 and row[0][0] == "Item"
                     and row[1][0] == "Unit"), None)
    if year_row is None:
        return []
    years = [value for label, count in year_row[2:] for value in [label] * count]
    if not years or any(not re.fullmatch(r"20\d{2}", year) for year in years):
        return []
    date_row = next((row for row in rows if len(row) == len(years)
                     and all(re.fullmatch(r"[A-Za-z]{3,9}\.?\s*\d{1,2}", cell[0]) for cell in row)), None)
    volume_index = next((index for index, row in enumerate(rows)
                         if len(row) == len(years) + 2 and row[1][0] == "Volume (Metric Tonnes)"), None)
    if date_row is None or volume_index is None or not any(
        row and row[0][0] == "1.2 Gold" for row in rows[max(0, volume_index - 3):volume_index]
    ):
        return []
    values = rows[volume_index][2:]
    result = []
    for (date_cell, _), year, (value_cell, _) in zip(date_row, years, values):
        match = re.fullmatch(r"([A-Za-z]{3,9})\.?\s*(\d{1,2})", date_cell)
        tonnes = _number(value_cell)
        if not match or tonnes is None or not 0 < tonnes < 10_000:
            return []
        try:
            period = datetime.strptime(f"{match.group(1)[:3]} {match.group(2)} {year}", "%b %d %Y").date()
        except ValueError:
            return []
        if period > release_date:
            return []
        result.append({"period": period.isoformat(), "tonnes": round(tonnes, 3),
                       "release_date": release_date.isoformat(), "url": source_url})
    return sorted(result, key=lambda row: row["period"])


def parse_safe_gold_html(text: str) -> list[dict[str, Any]]:
    """Lee exclusivamente la fila física 万盎司; nunca el valor en USD/SDR."""
    parser = _SafeTable()
    parser.feed(text)
    periods = next((re.findall(r"20\d{2}\.\d{2}", " ".join(row))
                    for row in parser.rows if len(re.findall(r"20\d{2}\.\d{2}", " ".join(row))) >= 2), [])
    quantity = next((row for row in parser.rows if sum("万盎司" in cell for cell in row) >= 2), [])
    rows = []
    if not periods or not quantity:
        return rows
    # Dos celdas idénticas por mes (USD y SDR); ambas expresan el mismo volumen.
    for index, period in enumerate(periods):
        first = 1 + 2 * index
        if first + 1 >= len(quantity):
            break
        left, right = quantity[first:first + 2]
        match = re.fullmatch(r"([\d,.]+)万盎司", left)
        if not match or left != right:
            continue
        ten_thousand_ounces = _number(match.group(1))
        if ten_thousand_ounces is None or ten_thousand_ounces <= 0:
            continue
        # 10 000 oz = 0.01 millones de onzas troy finas.
        rows.append({"period": period.replace(".", "-"),
                     "tonnes": _tonnes(ten_thousand_ounces / 100),
                     "release_policy": "publicación SAFE de la tabla anual"})
    return sorted(rows, key=lambda row: row["period"])


def _safe_html_url(index_html: str) -> str | None:
    match = re.search(r'href=["\'](/safe/\d{4}/[^"\']+\.html)["\'][^>]*>\s*html\s*<', index_html, re.I)
    return f"https://www.safe.gov.cn{match.group(1)}" if match else None


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


def _rbi_cache_within_limit(payload: dict[str, Any]) -> bool:
    for item in payload.get("reserves") or []:
        if not isinstance(item, dict) or item.get("id") != "rbi":
            continue
        if item.get("status") not in {"OK", "ARCHIVED", "STALE"}:
            return True
        try:
            age = (date.today() - date.fromisoformat(str(item["as_of"]))).days
            return 0 <= age <= 75
        except (KeyError, TypeError, ValueError):
            return False
    return True


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
    if identifier not in RESERVE_SCOPES:
        raise ValueError(f"Ámbito de reservas no reconocido: {identifier}")
    latest = rows[-1] if rows else None
    previous = rows[-2] if len(rows) >= 2 else None
    change = None
    if latest and previous:
        change = round(float(latest["tonnes"]) - float(previous["tonnes"]), 3)
    year_ago = None
    if latest and re.fullmatch(r"\d{4}-\d{2}", str(latest.get("period"))):
        target = f"{int(latest['period'][:4]) - 1}{latest['period'][4:]}"
        year_ago = next((row for row in rows if row.get("period") == target), None)
    return {
        "id": identifier,
        "label": label,
        "scope_kind": RESERVE_SCOPES[identifier][0],
        "scope_id": RESERVE_SCOPES[identifier][1],
        "measure_kind": "monetary_gold_stock",
        "unit": "metric_tonnes",
        "aggregation_allowed": False,
        "score_enabled": False,
        "status": "OK" if latest else "MISSING",
        "as_of": latest.get("period") if latest else None,
        "tonnes": latest.get("tonnes") if latest else None,
        "change_tonnes": change,
        "previous_as_of": previous.get("period") if previous else None,
        "change_kind": "difference_in_stocks" if change is not None else None,
        "change_interval": f"{previous['period']} → {latest['period']}" if change is not None else None,
        "change_12m_tonnes": round(float(latest["tonnes"]) - float(year_ago["tonnes"]), 3)
        if latest and year_ago else None,
        "year_ago_as_of": year_ago.get("period") if year_ago else None,
        "source": source,
        "source_url": source_url,
        "release_date": latest.get("release_date") if latest else None,
        # Las páginas utilizadas no proporcionan una hora de publicación
        # verificable por observación. Nunca inferirla del periodo/captura.
        "release_at": None,
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
    """Recupera saldos físicos oficiales; ante fallo conserva la última caché."""
    cached = _read_cache(cache_path)
    if (cached and cached.get("schema_version") == RESERVE_SCHEMA_VERSION
            and not refresh and _cache_fresh(cache_path) and _rbi_cache_within_limit(cached)):
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
        if previous and previous.get("status") in {"OK", "STALE"} and previous.get("tonnes") is not None:
            if identifier == "rbi":
                try:
                    if (date.today() - date.fromisoformat(str(previous["as_of"]))).days > 75:
                        return _reserve_record(identifier, label, source, source_url, [])
                except (KeyError, TypeError, ValueError):
                    return _reserve_record(identifier, label, source, source_url, [])
            record = dict(previous)
            record["status"] = "STALE"
            record["note"] = "Se muestra la última observación cacheada; la fuente no respondió."
            record.update({
                "scope_kind": RESERVE_SCOPES[identifier][0],
                "scope_id": RESERVE_SCOPES[identifier][1],
                "measure_kind": "monetary_gold_stock",
                "unit": "metric_tonnes",
                "aggregation_allowed": False,
                "score_enabled": False,
                "release_at": None,
            })
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

    try:
        safe_rows: list[dict[str, Any]] = []
        for index_url in (SAFE_INDEX_PREVIOUS, SAFE_INDEX_CURRENT):
            index = session.get(index_url, timeout=20)
            index.raise_for_status()
            table_url = _safe_html_url(index.text)
            if not table_url:
                raise ValueError("SAFE: sin enlace HTML de tabla")
            page = session.get(table_url, timeout=20)
            page.raise_for_status()
            # SAFE no siempre anuncia correctamente UTF-8; requests puede
            # interpretar el texto chino como Latin-1 y perder «万盎司».
            page.encoding = "utf-8"
            parsed = parse_safe_gold_html(page.text)
            if not parsed:
                raise ValueError("SAFE: sin cantidades físicas verificables")
            safe_rows.extend(parsed)
        safe_rows = list({row["period"]: row for row in safe_rows}.values())
        records.append(_reserve_record("safe", "China · SAFE", SAFE_SOURCE, SAFE_INDEX_CURRENT, sorted(safe_rows, key=lambda row: row["period"])))
    except Exception as exc:
        errors.append(f"China SAFE: {type(exc).__name__}")
        records.append(degraded_record("safe", "China · SAFE", SAFE_SOURCE, SAFE_INDEX_CURRENT))

    # La edición HTML de RBI aporta volumen físico y fecha del boletín. Si la
    # vigente solo enlaza PDF, un archivo anterior puede mostrarse como ARCHIVED
    # durante 75 días; nunca se presenta como dato vigente ni se puntúa.
    try:
        index = session.get(RBI_BULLETIN_INDEX, timeout=20)
        index.raise_for_status()
        html_links = parse_rbi_bulletin_html_links(index.text)
        archived = False
        if not html_links:
            archive_url = rbi_previous_bulletin_url(index.text)
            if archive_url:
                archive = session.get(archive_url, timeout=20)
                archive.raise_for_status()
                html_links = parse_rbi_bulletin_html_links(archive.text)
                archived = bool(html_links)
        if html_links:
            page = session.get(html_links[0], timeout=20)
            page.raise_for_status()
            rbi_rows = parse_rbi_gold_html(page.text, html_links[0])
            if not rbi_rows:
                raise ValueError("RBI: sin toneladas físicas y fechas verificables")
            latest = rbi_rows[-1]
            age = (date.today() - date.fromisoformat(latest["period"])).days
            if not 0 <= age <= 75:
                raise ValueError("RBI: observación demasiado antigua")
            if (date.today() - date.fromisoformat(latest["release_date"])).days < 0:
                raise ValueError("RBI: fecha de publicación futura")
            record = _reserve_record("rbi", "India · RBI", RBI_SOURCE, html_links[0], rbi_rows)
            if archived:
                record["status"] = "ARCHIVED"
                record["note"] += " Edición anterior verificada; la vigente solo enlaza PDF no validado."
            records.append(record)
        else:
            missing = _reserve_record("rbi", "India · RBI", RBI_SOURCE, RBI_BULLETIN_INDEX, [])
            missing["note"] = "La edición vigente no ofrece HTML verificable; PDF pendiente de extractor validado."
            records.append(missing)
    except Exception as exc:
        errors.append(f"India RBI: {type(exc).__name__}")
        records.append(degraded_record("rbi", "India · RBI", RBI_SOURCE, RBI_BULLETIN_INDEX))

    # NBP está rastreado, pero no se convierte valor monetario a toneladas.
    records.append(degraded_record("nbp", "Polonia · NBP", "NBP: balance de pagos, reservas físicas de oro",
                                   "https://static.nbp.pl/dane/bilans-platniczy/bopa_en.pdf"))

    if not records and cached:
        fallback = dict(cached)
        fallback["status"] = "STALE"
        fallback["errors"] = errors
        return fallback

    fresh = sum(item.get("status") == "OK" for item in records)
    stale = sum(item.get("status") == "STALE" for item in records)
    archived = sum(item.get("status") == "ARCHIVED" for item in records)
    available = fresh + stale + archived
    payload = {
        "schema_version": RESERVE_SCHEMA_VERSION,
        "status": "PARTIAL" if available else "MISSING",
        "coverage": {
            "available": available,
            "fresh": fresh,
            "stale": stale,
            "archived": archived,
            "missing": len(records) - available,
            "tracked": len(records),
            "basis": "tracked_sources_not_world",
            "world_total_available": False,
            "scope": "Fuentes rastreadas: BCE, EE. UU., China, India y Polonia. Saldo por entidad; no sumar como reservas o compras mundiales.",
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
    etf_holdings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    holdings = etf_holdings or {"status": "MISSING", "fund_id": "GLD", "history": [], "score_enabled": False}
    return {
        "status": (official or {}).get("status") or "MISSING",
        "official": official or {"status": "MISSING", "reserves": [], "score_enabled": False},
        "etf_market_proxy": build_etf_market_proxy(gld_points),
        "etf_holdings": holdings,
        # Un solo fondo no equivale al flujo agregado de los ETF de oro.
        "actual_etf_flows_status": "GLD_ONLY" if holdings.get("status") in {"OK", "STALE"} else "STANDBY",
        "score_enabled": False,
        "methodology": "Contexto separado del score hasta ampliar cobertura y validar valor incremental.",
    }
