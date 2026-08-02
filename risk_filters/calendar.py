"""
Filtro de Calendario Económico (calendar.py)

Detecta eventos macroeconómicos inminentes de alto impacto usando:
1. Fechas oficiales de publicación FRED (CPI, NFP, GDP, PCE, FOMC)
2. RSS verificado de Myfxbook (calendario económico)
3. Fechas FOMC/IPC manuales como respaldo informativo

Solo eventos macro de EE.UU. con impacto directo en SPY pueden bloquear señales.
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
    CALENDAR_BLOCK_HOURS_DEFAULT,
    CALENDAR_BLOCK_HOURS_STRICT,
    CALENDAR_BLOCKS_SIGNALS,
    CALENDAR_RSS_URL,
    CALENDAR_US_ONLY_BLOCKING,
)
from risk_filters.fred_calendar import fetch_fred_release_events
from user_settings import get_setting

US_BLOCKING_TERMS = [
    "cpi", "pce", "nfp", "nonfarm", "payroll", "fomc", "fed", "gdp",
    "jobless claims", "ism", "retail sales", "interest rate", "rate decision",
    "unemployment rate", "consumer confidence",
]

US_EVENT_PATTERNS = [
    r"^us\b",
    r"^u\.s\.\b",
    r"\bunited states\b",
    r"\busa\b",
    r"\bamerican\b",
    r"\bfomc\b",
    r"\bfederal reserve\b",
    r"\bfed\b",
    r"\bnonfarm\b",
    r"\bnfp\b",
    r"\bjobless claims\b",
]

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


def _is_us_event(title: str) -> bool:
    title_lower = title.lower().strip()
    return any(re.search(pattern, title_lower) for pattern in US_EVENT_PATTERNS)


def _is_us_blocking_event(title: str) -> bool:
    if not _is_us_event(title):
        return False
    title_lower = title.lower()
    return any(re.search(rf"\b{re.escape(term)}\b", title_lower) for term in US_BLOCKING_TERMS)


def _event_impact(title: str) -> str:
    if CALENDAR_US_ONLY_BLOCKING:
        if _is_us_blocking_event(title):
            return "ALTO"
        if _is_us_event(title):
            return "MEDIO"
        return "INFO"
    if _is_us_event(title):
        return "ALTO"
    return "MEDIO"


def _fetch_rss_events(lookahead_hours: int, now: datetime) -> List[Dict]:
    if feedparser is None:
        return []

    horizon = now + timedelta(hours=lookahead_hours)
    events: List[Dict] = []

    try:
        feed = feedparser.parse(CALENDAR_RSS_URL)
        for entry in feed.entries[:80]:
            title = (entry.get("title") or "").strip()
            if not title:
                continue

            event_time = _parse_event_time(entry)
            if event_time is None:
                continue
            if event_time < now - timedelta(hours=2) or event_time > horizon:
                continue

            hours_until = (event_time - now).total_seconds() / 3600
            impact = _event_impact(title)
            events.append({
                "title": title,
                "when_utc": event_time.isoformat(timespec="minutes"),
                "hours_until": round(hours_until, 1),
                "impact": impact,
                "source": CALENDAR_SOURCE,
                "verified": True,
                "us_event": _is_us_event(title),
                "blocks_signals": _is_us_blocking_event(title),
            })
    except Exception as exc:
        logging.warning(f"Error al leer calendario RSS: {exc}")

    return sorted(events, key=lambda item: item["hours_until"])


def _manual_fallback_events(lookahead_days: int, today: date, now: datetime) -> List[Dict]:
    horizon = [today + timedelta(days=d) for d in range(lookahead_days + 1)]
    events: List[Dict] = []

    for date_str in FOMC_DATES:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if event_date in horizon:
            when = "HOY" if event_date == today else f"en {(event_date - today).days} día(s)"
            event_dt = datetime.combine(event_date, datetime.min.time(), tzinfo=timezone.utc)
            events.append({
                "title": f"Reunión del FOMC (FED) {when} ({date_str})",
                "when_utc": event_dt.isoformat(timespec="minutes"),
                "hours_until": max(0.0, (event_dt - now).total_seconds() / 3600),
                "impact": "ALTO",
                "source": "estimado_manual",
                "verified": False,
                "us_event": True,
                "blocks_signals": False,
            })

    for date_str in CPI_DATES:
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        if event_date in horizon:
            when = "HOY" if event_date == today else f"en {(event_date - today).days} día(s)"
            event_dt = datetime.combine(event_date, datetime.min.time(), tzinfo=timezone.utc)
            events.append({
                "title": f"Publicación del IPC (Inflación) {when} ({date_str})",
                "when_utc": event_dt.isoformat(timespec="minutes"),
                "hours_until": max(0.0, (event_dt - now).total_seconds() / 3600),
                "impact": "ALTO",
                "source": "estimado_manual",
                "verified": False,
                "us_event": True,
                "blocks_signals": False,
            })

    return events


def build_calendar_context(calendar: Dict) -> Dict[str, object]:
    event = calendar.get("next_event") or {}
    title = str(event.get("title") or "").lower()
    if "cpi" in title or "inflation" in title:
        guidance, assets = "Riesgo de sorpresa de inflación y reacción de tipos.", ["SPY", "TLT", "UUP"]
    elif any(term in title for term in ("fomc", "fed", "rate")):
        guidance, assets = "Decisión de política monetaria; volatilidad elevada tras el anuncio.", ["SPY", "TLT", "UUP"]
    elif any(term in title for term in ("nfp", "employment", "payroll", "jobs")):
        guidance, assets = "El empleo puede modificar expectativas de tipos y dólar.", ["SPY", "TLT", "UUP"]
    else:
        guidance, assets = "Evento macro próximo; usarlo como contexto y confirmar tras la publicación.", ["SPY", "TLT"]
    return {"guidance": guidance, "affects_assets": assets, "confidence": calendar.get("confidence")}


def _event_family(title: str) -> str:
    """Agrupa nombres distintos de una misma publicación macroeconómica."""
    normalized = re.sub(r"\s+", " ", title.lower()).strip()
    families = (
        ("cpi", ("cpi", "consumer price", "ipc", "inflation")),
        ("fomc", ("fomc", "federal reserve")),
        ("nfp", ("nfp", "nonfarm", "payroll", "employment situation")),
        ("gdp", ("gdp", "gross domestic product")),
        ("pce", ("pce", "personal income", "personal consumption")),
    )
    for family, terms in families:
        if any(term in normalized for term in terms) or (family == "fomc" and re.search(r"\bfed\b", normalized)):
            return family
    return normalized


def _event_identity(event: Dict) -> tuple[str, str]:
    """Clave estable: mismo tipo de evento y misma fecha se muestra una sola vez."""
    raw_when = str(event.get("when_utc") or "")
    event_date = raw_when.split("T", 1)[0] if "T" in raw_when else raw_when[:10]
    return _event_family(str(event.get("title") or "")), event_date


def check_macro_events(
    lookahead_days: int = 1,
    lookahead_hours: int = 48,
    as_of: datetime | None = None,
    block_hours: int | None = None,
) -> Dict:
    """Comprueba eventos macro inminentes desde RSS verificado y respaldo manual."""
    now = as_of.astimezone(timezone.utc) if as_of is not None else datetime.now(timezone.utc)
    block_window = block_hours if block_hours in (3, 6) else get_setting("calendar_block_hours")
    fred_events = fetch_fred_release_events(lookahead_hours=lookahead_hours, now=now)
    rss_events = _fetch_rss_events(lookahead_hours=lookahead_hours, now=now)
    manual_events = _manual_fallback_events(lookahead_days=lookahead_days, today=now.date(), now=now)

    seen_events = set()
    merged: List[Dict] = []
    for event in fred_events + rss_events + manual_events:
        key = _event_identity(event)
        if key in seen_events:
            continue
        seen_events.add(key)
        merged.append(event)

    blocking_events = [
        event for event in merged
        if event.get("verified")
        and event.get("blocks_signals")
        and event.get("hours_until", 999) <= block_window
    ]

    warning_events = [
        event for event in merged
        if event.get("verified")
        and event.get("blocks_signals")
        and block_window == CALENDAR_BLOCK_HOURS_STRICT
        and CALENDAR_BLOCK_HOURS_STRICT < event.get("hours_until", 999) <= CALENDAR_BLOCK_HOURS_DEFAULT
    ]

    us_events = [event for event in merged if event.get("us_event") or event.get("blocks_signals")]
    display_pool = us_events if CALENDAR_US_ONLY_BLOCKING else merged
    display_events = [
        f"{event['title']} ({event.get('when_utc') or 'fecha estimada'})"
        for event in display_pool[:8]
    ]

    source = "fred_release" if fred_events else (CALENDAR_SOURCE if rss_events else "estimado_manual")
    confidence = "HIGH" if fred_events else (CALENDAR_CONFIDENCE if rss_events else "LOW")

    return {
        "event_imminent": len(display_pool) > 0,
        "should_block_signals": get_setting("calendar_blocks_signals") and CALENDAR_BLOCKS_SIGNALS and len(blocking_events) > 0,
        "events": display_events,
        "events_detail": merged,
        "blocking_events": blocking_events,
        "warning_events": warning_events,
        "block_hours": block_window,
        "source": source,
        "confidence": confidence,
        "next_event": display_pool[0] if display_pool else None,
        "us_only_blocking": CALENDAR_US_ONLY_BLOCKING,
    }
