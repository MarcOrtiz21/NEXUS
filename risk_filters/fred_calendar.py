"""
Calendario macro US vía fechas oficiales de publicación FRED.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Dict, List
from zoneinfo import ZoneInfo

import requests

from config import (
    FRED_API_KEY,
    FRED_CALENDAR_CACHE_FILE,
    FRED_CALENDAR_CACHE_TTL_SECONDS,
    FRED_CALENDAR_LOOKAHEAD_DAYS,
)

FRED_RELEASES = [
    {"release_id": 10, "label": "US CPI (Consumer Price Index)"},
    {"release_id": 50, "label": "US Employment Situation (NFP)"},
    {"release_id": 53, "label": "US Gross Domestic Product"},
    {"release_id": 21, "label": "US Personal Income and Outlays (PCE)"},
    {"release_id": 677, "label": "FOMC Press Release"},
]

# Zona horaria oficial de EE.UU. para publicaciones macro.
_US_EASTERN = ZoneInfo("America/New_York")

# Hora local ET real de cada tipo de publicación (por release_id de FRED).
# CPI/NFP/GDP/PCE se publican a 8:30 AM ET; FOMC anuncia a 2:00 PM ET.
RELEASE_TIMES_ET: Dict[int, time] = {
    10: time(8, 30),   # CPI
    50: time(8, 30),   # NFP
    53: time(8, 30),   # GDP
    21: time(8, 30),   # PCE
    677: time(14, 0),  # FOMC
}

_memory_cache: Dict[str, Any] | None = None


def clear_calendar_cache() -> None:
    """Limpia la caché en memoria (útil en tests)."""
    global _memory_cache
    _memory_cache = None


def _release_datetime(release_day: date, release_id: int) -> datetime:
    """Convierte fecha + release_id en un datetime UTC correcto (respeta DST)."""
    local_time = RELEASE_TIMES_ET.get(release_id, time(8, 30))
    local_dt = datetime.combine(release_day, local_time, tzinfo=_US_EASTERN)
    return local_dt.astimezone(timezone.utc)


def _cache_window(now: datetime) -> tuple[date, date]:
    start = (now - timedelta(days=1)).date()
    end = (now + timedelta(days=FRED_CALENDAR_LOOKAHEAD_DAYS)).date()
    return start, end


def _fetch_release_dates_api(release_id: int, start: date, end: date) -> List[Dict[str, str]]:
    params = {
        "release_id": release_id,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "sort_order": "asc",
        "include_release_dates_with_no_data": "true",
        "realtime_start": start.isoformat(),
        "realtime_end": end.isoformat(),
        "limit": 20,
    }
    resp = requests.get(
        "https://api.stlouisfed.org/fred/release/dates",
        params=params,
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json().get("release_dates", [])


def _load_disk_cache() -> Dict[str, Any] | None:
    if not FRED_CALENDAR_CACHE_FILE.exists():
        return None
    try:
        payload = json.loads(FRED_CALENDAR_CACHE_FILE.read_text(encoding="utf-8"))
        captured_raw = payload.get("captured_at")
        if captured_raw:
            captured = datetime.fromisoformat(captured_raw.replace("Z", "+00:00"))
            if captured.tzinfo is None:
                captured = captured.replace(tzinfo=timezone.utc)
            payload["_captured_at_dt"] = captured.astimezone(timezone.utc)
        return payload
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        logging.warning(f"No se pudo leer caché FRED calendar: {exc}")
        return None


def _save_disk_cache(payload: Dict[str, Any]) -> None:
    try:
        FRED_CALENDAR_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        clean = {k: v for k, v in payload.items() if not k.startswith("_")}
        tmp = FRED_CALENDAR_CACHE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(FRED_CALENDAR_CACHE_FILE)
    except OSError as exc:
        logging.warning(f"No se pudo guardar caché FRED calendar: {exc}")


def _cache_is_fresh(payload: Dict[str, Any], now: datetime, start: date, end: date) -> bool:
    captured = payload.get("_captured_at_dt")
    if captured is None:
        return False
    age = (now - captured).total_seconds()
    if age > FRED_CALENDAR_CACHE_TTL_SECONDS:
        return False
    return payload.get("window_start") == start.isoformat() and payload.get("window_end") == end.isoformat()


def _get_cached_release_dates(now: datetime, force: bool = False) -> Dict[str, List[Dict[str, str]]]:
    """Devuelve fechas crudas por release_id; refresca como máximo 5 HTTP cada TTL."""
    global _memory_cache

    if not FRED_API_KEY:
        return {}

    start, end = _cache_window(now)

    if not force and _memory_cache is not None and _cache_is_fresh(_memory_cache, now, start, end):
        return _memory_cache["releases"]

    disk = _load_disk_cache()
    if not force and disk and _cache_is_fresh(disk, now, start, end):
        _memory_cache = {
            "captured_at": disk["captured_at"],
            "_captured_at_dt": disk["_captured_at_dt"],
            "window_start": disk["window_start"],
            "window_end": disk["window_end"],
            "releases": disk["releases"],
        }
        logging.info("Usando caché FRED release calendar...")
        return disk["releases"]

    stale_disk = disk
    releases: Dict[str, List[Dict[str, str]]] = {}
    failed = 0

    for release in FRED_RELEASES:
        release_id = release["release_id"]
        key = str(release_id)
        try:
            releases[key] = _fetch_release_dates_api(release_id, start, end)
        except Exception as exc:
            failed += 1
            logging.warning(f"Error al leer calendario FRED release {release_id}: {exc}")
            if stale_disk and key in stale_disk.get("releases", {}):
                releases[key] = stale_disk["releases"][key]

    if not releases and stale_disk:
        logging.info("Usando caché FRED release calendar obsoleta (API no disponible)...")
        return stale_disk.get("releases", {})

    if failed == len(FRED_RELEASES) and stale_disk:
        logging.info("Usando caché FRED release calendar obsoleta (API no disponible)...")
        return stale_disk.get("releases", {})

    payload = {
        "captured_at": now.isoformat(timespec="seconds"),
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "releases": releases,
    }
    _save_disk_cache(payload)
    _memory_cache = {
        **payload,
        "_captured_at_dt": now,
    }
    return releases


def _events_from_cached_dates(
    cached: Dict[str, List[Dict[str, str]]],
    lookahead_hours: int,
    now: datetime,
) -> List[Dict]:
    horizon = now + timedelta(hours=lookahead_hours)
    events: List[Dict] = []

    for release in FRED_RELEASES:
        release_id = release["release_id"]
        for item in cached.get(str(release_id), []):
            raw_date = item.get("date")
            if not raw_date:
                continue
            try:
                release_day = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                continue
            event_time = _release_datetime(release_day, release_id)
            if event_time < now - timedelta(hours=2) or event_time > horizon:
                continue
            hours_until = (event_time - now).total_seconds() / 3600
            events.append({
                "title": release["label"],
                "when_utc": event_time.isoformat(timespec="minutes"),
                "hours_until": round(hours_until, 1),
                "impact": "ALTO",
                "source": "fred_release",
                "verified": True,
                "us_event": True,
                "blocks_signals": True,
            })

    return sorted(events, key=lambda item: item["hours_until"])


def fetch_fred_release_events(lookahead_hours: int, now: datetime) -> List[Dict]:
    cached = _get_cached_release_dates(now)
    return _events_from_cached_dates(cached, lookahead_hours, now)
