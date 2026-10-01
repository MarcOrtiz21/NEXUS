"""Calendario oficial de reuniones del FOMC (federalreserve.gov).

La decisión se publica el último día de cada reunión a las 14:00 ET. Las
fechas se extraen de la página oficial y se guardan en caché local; si la
página no responde se usa la caché aunque esté caducada.
"""

from __future__ import annotations

import html
import json
import logging
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import requests

from config import FOMC_CALENDAR_CACHE_FILE, FOMC_CALENDAR_CACHE_TTL_SECONDS, FOMC_CALENDAR_URL

FOMC_SOURCE = "fed_fomc_calendar"
FOMC_TITLE = "FOMC: decisión de tipos de la Fed"
_EASTERN = ZoneInfo("America/New_York")
_MONTHS = {
    name: index for index, name in enumerate(
        ("january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"), start=1)
}
_YEAR_HEADER = re.compile(r">\s*(\d{4}) FOMC Meetings\s*<")
_MEETING = re.compile(
    r'fomc-meeting__month[^>]*>\s*(?:<strong>)?\s*([A-Za-z/]+)\s*(?:</strong>)?\s*</div>\s*'
    r'<div class="fomc-meeting__date[^>]*>\s*([^<]+?)\s*</div>',
    re.S,
)

_RETRY_AFTER = timedelta(minutes=15)
_memory_cache: Dict[str, Any] | None = None
_last_failure: datetime | None = None


def clear_fomc_cache() -> None:
    global _memory_cache, _last_failure
    _memory_cache = None
    _last_failure = None


def _month_number(name: str) -> int | None:
    name = name.strip().lower()
    if name in _MONTHS:
        return _MONTHS[name]
    matches = [index for full, index in _MONTHS.items() if full.startswith(name[:3])] if len(name) >= 3 else []
    return matches[0] if matches else None


def _decision_date(year: int, month_text: str, day_text: str) -> date | None:
    """Último día de la reunión; admite «Apr/May» + «30-1» y marcas como «*»."""
    if "unscheduled" in day_text.lower() or "notation" in day_text.lower():
        return None
    months = [_month_number(part) for part in month_text.split("/") if part.strip()]
    days = [int(value) for value in re.findall(r"\d+", day_text)]
    if not months or None in months or not days:
        return None
    month = months[-1]
    try:
        return date(year, month, days[-1])
    except ValueError:
        return None


def parse_fomc_calendar(content: str) -> List[date]:
    """Devuelve las fechas de decisión de todas las reuniones programadas."""
    content = html.unescape(content)
    headers = [(match.start(), int(match.group(1))) for match in _YEAR_HEADER.finditer(content)]
    decisions: set[date] = set()
    for index, (start, year) in enumerate(headers):
        end = headers[index + 1][0] if index + 1 < len(headers) else len(content)
        for month_text, day_text in _MEETING.findall(content[start:end]):
            decided = _decision_date(year, month_text, day_text)
            if decided is not None:
                decisions.add(decided)
    return sorted(decisions)


def decision_datetime(day: date) -> datetime:
    return datetime.combine(day, time(14, 0), tzinfo=_EASTERN).astimezone(timezone.utc)


def _read_cache(path: Path) -> Dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("decisions"), list):
        return None
    return payload


def _write_cache(path: Path, payload: Dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
    except OSError as exc:
        logging.warning(f"No se pudo guardar caché FOMC: {exc}")


def fomc_decision_dates(
    now: datetime | None = None,
    *,
    cache_path: Path = FOMC_CALENDAR_CACHE_FILE,
    session: Any = None,
) -> List[date]:
    """Fechas oficiales de decisión, con caché en memoria y en disco."""
    global _memory_cache, _last_failure
    now = now or datetime.now(timezone.utc)

    def fresh(payload: Dict[str, Any] | None) -> bool:
        try:
            captured = datetime.fromisoformat(str((payload or {}).get("captured_at")))
        except ValueError:
            return False
        return (now - captured).total_seconds() <= FOMC_CALENDAR_CACHE_TTL_SECONDS

    if _memory_cache and fresh(_memory_cache):
        return [date.fromisoformat(value) for value in _memory_cache["decisions"]]
    disk = _read_cache(cache_path)
    if disk and fresh(disk):
        _memory_cache = disk
        return [date.fromisoformat(value) for value in disk["decisions"]]
    if _last_failure is not None and now - _last_failure < _RETRY_AFTER:
        return [date.fromisoformat(value) for value in (disk or {}).get("decisions", [])]

    try:
        response = (session or requests).get(
            FOMC_CALENDAR_URL, timeout=10,
            headers={"User-Agent": "NEXUS/1.0 (+local workstation)"},
        )
        response.raise_for_status()
        decisions = parse_fomc_calendar(response.text)
        if not decisions:
            raise ValueError("la página FOMC no contiene reuniones reconocibles")
    except Exception as exc:
        logging.warning(f"Error al leer calendario FOMC: {exc}")
        _last_failure = now
        if disk:
            return [date.fromisoformat(value) for value in disk["decisions"]]
        return []

    payload = {
        "source": FOMC_SOURCE,
        "url": FOMC_CALENDAR_URL,
        "captured_at": now.isoformat(timespec="seconds"),
        "decisions": [day.isoformat() for day in decisions],
    }
    _write_cache(cache_path, payload)
    _memory_cache = payload
    _last_failure = None
    return decisions


def fetch_fomc_events(lookahead_hours: int, now: datetime) -> List[Dict]:
    horizon = now + timedelta(hours=lookahead_hours)
    events = []
    for day in fomc_decision_dates(now):
        when = decision_datetime(day)
        if when < now - timedelta(hours=2) or when > horizon:
            continue
        events.append({
            "title": FOMC_TITLE,
            "when_utc": when.isoformat(timespec="minutes"),
            "hours_until": round((when - now).total_seconds() / 3600, 1),
            "impact": "ALTO",
            "source": FOMC_SOURCE,
            "verified": True,
            "us_event": True,
            "blocks_signals": True,
        })
    return sorted(events, key=lambda item: item["hours_until"])
