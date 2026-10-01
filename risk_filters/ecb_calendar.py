"""Calendario oficial de reuniones de política monetaria del BCE (ecb.europa.eu).

La decisión se publica el último día de cada reunión de política monetaria a
las 14:15 hora de Frankfurt. Las reuniones no monetarias y las del Consejo
General se descartan. Reutilización permitida citando la fuente (BCE).
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

from config import ECB_CALENDAR_CACHE_FILE, ECB_CALENDAR_CACHE_TTL_SECONDS, ECB_CALENDAR_URL
from risk_filters.official_calendar import OfficialDecisionCalendar

ECB_SOURCE = "ecb_meeting_calendar"
ECB_TITLE = "ECB: decisión de tipos del BCE"
_FRANKFURT = ZoneInfo("Europe/Berlin")
_ENTRY = re.compile(r"<dt>\s*(\d{2})/(\d{2})/(\d{4})\s*</dt>\s*<dd>(.*?)</dd>", re.S)


def _is_decision_day(description: str) -> bool:
    text = re.sub(r"<[^>]+>", " ", description).lower()
    if "monetary policy meeting" not in text or "non-monetary" in text:
        return False
    return "day 1" not in text


def parse_ecb_calendar(content: str) -> List[date]:
    """Devuelve las fechas de decisión de las reuniones de política monetaria."""
    content = html.unescape(content)
    decisions: set[date] = set()
    for day, month, year, description in _ENTRY.findall(content):
        if not _is_decision_day(description):
            continue
        try:
            decisions.add(date(int(year), int(month), int(day)))
        except ValueError:
            continue
    # Algunos primeros días de reunión no llevan la marca «Day 1».
    return sorted(day for day in decisions if day + timedelta(days=1) not in decisions)


def decision_datetime(day: date) -> datetime:
    return datetime.combine(day, time(14, 15), tzinfo=_FRANKFURT).astimezone(timezone.utc)


_CALENDAR = OfficialDecisionCalendar(
    source=ECB_SOURCE,
    url=ECB_CALENDAR_URL,
    cache_path=ECB_CALENDAR_CACHE_FILE,
    ttl_seconds=ECB_CALENDAR_CACHE_TTL_SECONDS,
    parser=parse_ecb_calendar,
)


def clear_ecb_cache() -> None:
    _CALENDAR.clear()


def ecb_decision_dates(
    now: datetime | None = None,
    *,
    cache_path: Path | None = None,
    session: Any = None,
) -> List[date]:
    return _CALENDAR.decision_dates(now or datetime.now(timezone.utc), cache_path=cache_path, session=session)


def fetch_ecb_events(lookahead_hours: int, now: datetime) -> List[Dict]:
    horizon = now + timedelta(hours=lookahead_hours)
    events = []
    for day in ecb_decision_dates(now):
        when = decision_datetime(day)
        if when < now - timedelta(hours=2) or when > horizon:
            continue
        events.append({
            "title": ECB_TITLE,
            "when_utc": when.isoformat(timespec="minutes"),
            "hours_until": round((when - now).total_seconds() / 3600, 1),
            "impact": "ALTO",
            "source": ECB_SOURCE,
            "verified": True,
            "us_event": False,
            "blocks_signals": False,
        })
    return sorted(events, key=lambda item: item["hours_until"])
