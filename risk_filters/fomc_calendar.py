"""Calendario oficial de reuniones del FOMC (federalreserve.gov).

La decisión se publica el último día de cada reunión a las 14:00 ET.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from config import FOMC_CALENDAR_CACHE_FILE, FOMC_CALENDAR_CACHE_TTL_SECONDS, FOMC_CALENDAR_URL
from risk_filters.official_calendar import OfficialDecisionCalendar

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


_CALENDAR = OfficialDecisionCalendar(
    source=FOMC_SOURCE,
    url=FOMC_CALENDAR_URL,
    cache_path=FOMC_CALENDAR_CACHE_FILE,
    ttl_seconds=FOMC_CALENDAR_CACHE_TTL_SECONDS,
    parser=parse_fomc_calendar,
)


def clear_fomc_cache() -> None:
    _CALENDAR.clear()


def fomc_decision_dates(
    now: datetime | None = None,
    *,
    cache_path: Path | None = None,
    session: Any = None,
) -> List[date]:
    """Fechas oficiales de decisión, con caché en memoria y en disco."""
    return _CALENDAR.decision_dates(now or datetime.now(timezone.utc), cache_path=cache_path, session=session)


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
