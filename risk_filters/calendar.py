"""
Filtro de Calendario Económico (calendar.py)

Detecta eventos macroeconómicos inminentes de alto impacto usando:
1. RSS verificado de Myfxbook (calendario económico)
2. Fechas FOMC/IPC manuales como respaldo informativo
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List

try:
    import feedparser
except ImportError:
    feedparser = None

from config import (
    CALENDAR_BLOCK_HOURS,
    CALENDAR_BLOCK_HOURS_DEFAULT,
    CALENDAR_BLOCK_HOURS_STRICT,
    CALENDAR_BLOCKS_SIGNALS,
    CALENDAR_RSS_URL,
)

HIGH_IMPACT_TERMS = [
    "fomc", "fed", "federal reserve", "interest rate", "rate decision",
    "cpi", "inflation", "pce", "nfp", "nonfarm", "payroll", "gdp",
    "retail sales", "ism", "pmi", "jobless claims", "unemployment",
    "ecb", "boe", "boj", "pboc",
]

US_TERMS = ["us ", " u.s.", "united states", "usa", "american"]

CALENDAR_SOURCE = "myfxbook_rss"
CALENDAR_CONFIDENCE = "MEDIUM"

FOMC_DATES = [
    "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
]

CPI_DATES = [
    "2026-01-13", "2026-02-11", "2026-03-10", "2026-04-14",
    "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
    "2026-09-15", "2026-10-13", "2026-11-10", "2026-12-10",
]


def _parse_event_time(entry) -> datetime | None:
    for field in ("published", "updated", "published_parsed", "updated_parsed"):
        raw = entry.get(field)
        if not raw:
            continue
        try:
            if isinstance(raw, str):
                return parsedate_to_datetime(raw).astimezone(timezone.utc)
            if hasattr(raw, "tm_year"):
                return datetime(*raw[:6], tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def _is_high_impact(title: str) -> bool:
    title_lower = title.lower()
    return any(term in title_lower for term in HIGH_IMPACT_TERMS)


def _is_us_event(title: str) -> bool:
    title_lower = f" {title.lower()} "
    return any(term in title_lower for term in US_TERMS) or title_lower.strip().startswith("us ")


def _fetch_rss_events(lookahead_hours: int, now: datetime) -> List[Dict]:
    if feedparser is None:
        return []

    horizon = now + timedelta(hours=lookahead_hours)
    events: List[Dict] = []

    try:
        feed = feedparser.parse(CALENDAR_RSS_URL)
        for entry in feed.entries[:80]:
            title = (entry.get("title") or "").strip()
            if not title or not _is_high_impact(title):
                continue

            event_time = _parse_event_time(entry)
            if event_time is None:
                continue
            if event_time < now - timedelta(hours=2) or event_time > horizon:
                continue

            hours_until = (event_time - now).total_seconds() / 3600
            impact = "ALTO" if _is_us_event(title) else "MEDIO"
            events.append({
                "title": title,
                "when_utc": event_time.isoformat(timespec="minutes"),
                "hours_until": round(hours_until, 1),
                "impact": impact,
                "source": CALENDAR_SOURCE,
                "verified": True,
            })
    except Exception as exc:
        logging.warning(f"Error al leer calendario RSS: {exc}")

    return sorted(events, key=lambda item: item["hours_until"])


def _manual_fallback_events(lookahead_days: int, today: date) -> List[Dict]:
    horizon = [today + timedelta(days=d) for d in range(lookahead_days + 1)]
    events: List[Dict] = []

    for date_str in FOMC_DATES:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if event_date in horizon:
            when = "HOY" if event_date == today else f"en {(event_date - today).days} día(s)"
            events.append({
                "title": f"Reunión del FOMC (FED) {when} ({date_str})",
                "when_utc": None,
                "hours_until": max(0.0, (datetime.combine(event_date, datetime.min.time(), tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 3600),
                "impact": "ALTO",
                "source": "estimado_manual",
                "verified": False,
            })

    for date_str in CPI_DATES:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if event_date in horizon:
            when = "HOY" if event_date == today else f"en {(event_date - today).days} día(s)"
            events.append({
                "title": f"Publicación del IPC (Inflación) {when} ({date_str})",
                "when_utc": None,
                "hours_until": max(0.0, (datetime.combine(event_date, datetime.min.time(), tzinfo=timezone.utc) - datetime.now(timezone.utc)).total_seconds() / 3600),
                "impact": "ALTO",
                "source": "estimado_manual",
                "verified": False,
            })

    return events


def check_macro_events(
    lookahead_days: int = 1,
    lookahead_hours: int = 48,
    as_of: datetime | None = None,
    block_hours: int | None = None,
) -> Dict:
    """Comprueba eventos macro inminentes desde RSS verificado y respaldo manual."""
    now = as_of.astimezone(timezone.utc) if as_of is not None else datetime.now(timezone.utc)
    block_window = block_hours if block_hours in (3, 6) else CALENDAR_BLOCK_HOURS
    rss_events = _fetch_rss_events(lookahead_hours=lookahead_hours, now=now)
    manual_events = _manual_fallback_events(lookahead_days=lookahead_days, today=now.date())

    seen_titles = set()
    merged: List[Dict] = []
    for event in rss_events + manual_events:
        key = re.sub(r"\s+", " ", event["title"].lower())
        if key in seen_titles:
            continue
        seen_titles.add(key)
        merged.append(event)

    blocking_events = [
        event for event in merged
        if event.get("verified")
        and event.get("impact") == "ALTO"
        and event.get("hours_until", 999) <= block_window
    ]

    warning_events = [
        event for event in merged
        if event.get("verified")
        and event.get("impact") == "ALTO"
        and block_window == CALENDAR_BLOCK_HOURS_STRICT
        and CALENDAR_BLOCK_HOURS_STRICT < event.get("hours_until", 999) <= CALENDAR_BLOCK_HOURS_DEFAULT
    ]

    display_events = [
        f"{event['title']} ({event.get('when_utc') or 'fecha estimada'})"
        for event in merged[:8]
    ]

    source = CALENDAR_SOURCE if rss_events else "estimado_manual"
    confidence = CALENDAR_CONFIDENCE if rss_events else "LOW"

    return {
        "event_imminent": len(merged) > 0,
        "should_block_signals": CALENDAR_BLOCKS_SIGNALS and len(blocking_events) > 0,
        "events": display_events,
        "events_detail": merged,
        "blocking_events": blocking_events,
        "warning_events": warning_events,
        "block_hours": block_window,
        "source": source,
        "confidence": confidence,
        "next_event": merged[0] if merged else None,
    }


if __name__ == "__main__":
    res = check_macro_events()
    print("Estado del calendario económico:")
    if res["event_imminent"]:
        for ev in res["events"]:
            print(f"  ⚠️ {ev}")
        if res["should_block_signals"]:
            print("  🛑 Bloqueo de señales ACTIVO por evento verificado de alto impacto.")
    else:
        print("  ✅ No hay eventos macro inminentes.")
