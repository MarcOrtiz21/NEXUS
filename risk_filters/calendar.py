"""
Filtro de Calendario Económico (calendar.py)

Detecta eventos macroeconómicos inminentes de alto impacto usando:
1. Fechas oficiales de publicación FRED (CPI, NFP, PIB, PCE, PPI, ventas minoristas, subsidios, JOLTS)
2. Calendarios oficiales de reuniones del FOMC (federalreserve.gov) y del BCE (ecb.europa.eu)
3. Fechas FOMC/IPC manuales como respaldo informativo

Solo eventos macro de EE.UU. con impacto directo en SPY pueden bloquear señales.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List

from config import (
    CALENDAR_BLOCK_HOURS_DEFAULT,
    CALENDAR_BLOCK_HOURS_STRICT,
    CALENDAR_BLOCKS_SIGNALS,
    CALENDAR_US_ONLY_BLOCKING,
)
from risk_filters.ecb_calendar import ECB_SOURCE, fetch_ecb_events
from risk_filters.fomc_calendar import FOMC_SOURCE, fetch_fomc_events
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

# Respaldo si la página oficial de la Fed no responde y no hay caché.
FOMC_DATES = [
    "2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17",
    "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09",
    "2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09",
    "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08",
]

CPI_DATES = [
    "2026-01-13", "2026-02-11", "2026-03-10", "2026-04-14",
    "2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12",
    "2026-09-15", "2026-10-13", "2026-11-10", "2026-12-10",
]


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


_FX_GOLD_TITLE_TERMS = (
    "fomc",
    "federal reserve",
    "cpi",
    "pce",
    "nfp",
    "nonfarm",
    "non-farm",
    "payroll",
    "ipc",
    "ppi",
    "producer price",
    "retail sales",
)


def is_fx_gold_calendar_event(title: str) -> bool:
    """FOMC, CPI/PCE, NFP y BCE: lo que mueve EUR/USD y el oro en 72h."""
    text = str(title or "").lower()
    if re.search(r"\becb\b", text) or "european central" in text:
        return True
    if not (_is_us_event(title) or "fomc" in text):
        return False
    if re.search(r"\bfed\b", text):
        return True
    return any(term in text for term in _FX_GOLD_TITLE_TERMS)


def fx_gold_upcoming_events(
    events: List[Dict] | None,
    lookahead_hours: float = 72,
    limit: int = 8,
) -> List[Dict]:
    selected: List[Dict] = []
    for event in events or []:
        hours = event.get("hours_until")
        if not isinstance(hours, (int, float)) or hours < 0 or hours > lookahead_hours:
            continue
        if not is_fx_gold_calendar_event(str(event.get("title") or "")):
            continue
        selected.append(event)
    selected.sort(key=lambda item: float(item.get("hours_until") or 0))
    return selected[:limit]


def gold_monthly_events(
    *,
    as_of: datetime | None = None,
    lookahead_days: int = 31,
    limit: int = 12,
) -> List[Dict]:
    """Calendario mensual del oro con fuente oficial y respaldo manual.

    Se mantiene separado del filtro operativo de 72 horas: un evento lejano
    aporta contexto, pero nunca bloquea señales antes de entrar en la ventana
    configurada. FRED y la Fed tienen prioridad sobre el respaldo manual para evitar
    duplicados del mismo evento y fecha.
    """
    now = as_of.astimezone(timezone.utc) if as_of is not None else datetime.now(timezone.utc)
    lookahead_hours = max(1, lookahead_days) * 24
    official = fetch_fred_release_events(lookahead_hours=lookahead_hours, now=now)
    official += fetch_fomc_events(lookahead_hours=lookahead_hours, now=now)
    official += fetch_ecb_events(lookahead_hours=lookahead_hours, now=now)
    fallback = _manual_fallback_events(
        lookahead_days=max(1, lookahead_days),
        today=now.date(),
        now=now,
    )
    seen: set[tuple[str, str]] = set()
    merged: List[Dict] = []
    for raw_event in official + fallback:
        if not is_fx_gold_calendar_event(str(raw_event.get("title") or "")):
            continue
        identity = _event_identity(raw_event)
        if identity in seen:
            continue
        seen.add(identity)
        event = dict(raw_event)
        event["time_quality"] = _calendar_time_quality(event.get("source"))
        event["estimated"] = event["time_quality"] == "aproximada"
        merged.append(event)
    merged.sort(key=lambda item: float(item.get("hours_until") or 0))
    return merged[:limit]


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


def _is_official_source(source: str | None) -> bool:
    src = str(source or "").lower()
    return "fred" in src or src in (FOMC_SOURCE, ECB_SOURCE)


def _calendar_time_quality(source: str | None) -> str:
    return "oficial" if _is_official_source(source) else "aproximada"


def _quality_from_events(events: List[Dict], fallback_source: str, fallback_confidence: str) -> tuple[str, str, str]:
    if not events:
        return fallback_source, fallback_confidence, _calendar_time_quality(fallback_source)
    source = str(events[0].get("source") or fallback_source)
    if _is_official_source(source):
        return source, "HIGH", "oficial"
    return source, "LOW", "aproximada"


def check_macro_events(
    lookahead_days: int = 1,
    lookahead_hours: int = 48,
    as_of: datetime | None = None,
    block_hours: int | None = None,
) -> Dict:
    """Comprueba eventos macro inminentes desde fuentes oficiales y respaldo manual."""
    now = as_of.astimezone(timezone.utc) if as_of is not None else datetime.now(timezone.utc)
    block_window = block_hours if block_hours in (3, 6) else get_setting("calendar_block_hours")
    fred_events = fetch_fred_release_events(lookahead_hours=lookahead_hours, now=now)
    fomc_events = fetch_fomc_events(lookahead_hours=lookahead_hours, now=now)
    ecb_events = fetch_ecb_events(lookahead_hours=lookahead_hours, now=now)
    manual_events = _manual_fallback_events(lookahead_days=lookahead_days, today=now.date(), now=now)
    gold_events_30d = gold_monthly_events(as_of=now)

    seen_events = set()
    merged: List[Dict] = []
    for event in fred_events + fomc_events + ecb_events + manual_events:
        key = _event_identity(event)
        if key in seen_events:
            continue
        seen_events.add(key)
        event = dict(event)
        event["time_quality"] = _calendar_time_quality(event.get("source"))
        event["estimated"] = event["time_quality"] == "aproximada"
        merged.append(event)
    merged.sort(key=lambda item: float(item.get("hours_until") or 0))

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

    source = "fred_release" if fred_events else (FOMC_SOURCE if fomc_events else "estimado_manual")
    confidence = "HIGH" if fred_events or fomc_events else "LOW"
    anchor = blocking_events[0] if blocking_events else (display_pool[0] if display_pool else None)
    block_source, block_confidence, time_quality = _quality_from_events(
        [anchor] if anchor else [],
        source,
        confidence,
    )

    return {
        "event_imminent": len(display_pool) > 0,
        "should_block_signals": get_setting("calendar_blocks_signals") and CALENDAR_BLOCKS_SIGNALS and len(blocking_events) > 0,
        "events": display_events,
        "events_detail": merged,
        "gold_events_30d": gold_events_30d,
        "blocking_events": blocking_events,
        "warning_events": warning_events,
        "block_hours": block_window,
        "source": block_source if blocking_events else source,
        "confidence": block_confidence if blocking_events else confidence,
        "time_quality": time_quality,
        "next_event": blocking_events[0] if blocking_events else (display_pool[0] if display_pool else None),
        "us_only_blocking": CALENDAR_US_ONLY_BLOCKING,
    }
