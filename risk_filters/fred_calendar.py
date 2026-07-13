"""
Calendario macro US vía fechas oficiales de publicación FRED.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List

import requests

from config import FRED_API_KEY

FRED_RELEASES = [
    {"release_id": 10, "label": "US CPI (Consumer Price Index)"},
    {"release_id": 50, "label": "US Employment Situation (NFP)"},
    {"release_id": 53, "label": "US Gross Domestic Product"},
    {"release_id": 21, "label": "US Personal Income and Outlays (PCE)"},
    {"release_id": 677, "label": "FOMC Press Release"},
]

# Publicaciones macro US habituales: 8:30 ET ≈ 12:30 UTC (horario estándar aproximado).
US_RELEASE_HOUR_UTC = 12
US_RELEASE_MINUTE_UTC = 30


def _release_datetime(release_day: date) -> datetime:
    return datetime.combine(
        release_day,
        time(US_RELEASE_HOUR_UTC, US_RELEASE_MINUTE_UTC),
        tzinfo=timezone.utc,
    )


def fetch_fred_release_events(lookahead_hours: int, now: datetime) -> List[Dict]:
    if not FRED_API_KEY:
        return []

    horizon = now + timedelta(hours=lookahead_hours)
    start = now.date().isoformat()
    end = (now + timedelta(days=max(1, lookahead_hours // 24 + 2))).date().isoformat()
    events: List[Dict] = []

    for release in FRED_RELEASES:
        params = {
            "release_id": release["release_id"],
            "api_key": FRED_API_KEY,
            "file_type": "json",
            "sort_order": "asc",
            "include_release_dates_with_no_data": "true",
            "realtime_start": start,
            "realtime_end": end,
            "limit": 20,
        }
        try:
            resp = requests.get(
                "https://api.stlouisfed.org/fred/release/dates",
                params=params,
                timeout=10,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as exc:
            logging.warning(f"Error al leer calendario FRED release {release['release_id']}: {exc}")
            continue

        for item in payload.get("release_dates", []):
            raw_date = item.get("date")
            if not raw_date:
                continue
            try:
                release_day = datetime.strptime(raw_date, "%Y-%m-%d").date()
            except ValueError:
                continue
            event_time = _release_datetime(release_day)
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
