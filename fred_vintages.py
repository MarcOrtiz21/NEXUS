"""Lectura point-in-time de FRED/ALFRED para el motor histórico de oro.

Se usa ``output_type=4``: conserva el valor de primera publicación de cada
periodo y su ``realtime_start``. Así una simulación solo puede ver datos cuya
fecha de publicación sea anterior o igual a su fecha de corte.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable

import requests

from config import FRED_API_KEY, FRED_VINTAGE_CACHE_DIR


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
VINTAGE_CACHE_TTL_SECONDS = 60 * 60 * 24


def _day(value: str | date | datetime) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def parse_initial_releases(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normaliza observaciones y descarta valores ausentes o incoherentes."""
    result: list[dict[str, Any]] = []
    for raw in payload.get("observations") or []:
        try:
            period = _day(raw["date"])
            release = _day(raw["realtime_start"])
            value = float(raw["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(value) or release < period:
            continue
        result.append({
            "period": period.isoformat(),
            "release_at": release.isoformat(),
            "realtime_end": str(raw.get("realtime_end") or "")[:10] or None,
            "value": value,
        })
    return sorted(result, key=lambda item: (item["period"], item["release_at"]))


def _cache_path(series_id: str, observation_start: str, observation_end: str, cache_dir: Path) -> Path:
    token = hashlib.sha256(f"{series_id}:{observation_start}:{observation_end}".encode()).hexdigest()[:12]
    return cache_dir / f"{series_id}_{token}.json"


def fetch_initial_releases(
    series_id: str,
    observation_start: str,
    observation_end: str,
    *,
    api_key: str | None = FRED_API_KEY,
    cache_dir: Path = FRED_VINTAGE_CACHE_DIR,
    refresh: bool = False,
    request_get: Callable[..., Any] = requests.get,
) -> list[dict[str, Any]]:
    """Descarga primeras publicaciones de ALFRED con caché local auditable."""
    if not api_key:
        raise RuntimeError("FRED_API_KEY no está configurada")
    start = _day(observation_start).isoformat()
    end = _day(observation_end).isoformat()
    if start > end:
        raise ValueError("observation_start no puede ser posterior a observation_end")
    cache_dir = Path(cache_dir)
    path = _cache_path(series_id, start, end, cache_dir)
    if not refresh and path.exists() and time.time() - path.stat().st_mtime <= VINTAGE_CACHE_TTL_SECONDS:
        cached = json.loads(path.read_text(encoding="utf-8"))
        return list(cached.get("observations") or [])

    # FRED limita a 2.000 vintage dates por respuesta. Las series diarias
    # superan ese límite en diez años, por lo que se divide el periodo real
    # (fecha de conocimiento) en tramos sin alterar el periodo observado.
    rows: list[dict[str, Any]] = []
    chunk_start = _day(start)
    final_day = _day(end)
    while chunk_start <= final_day:
        chunk_end = min(final_day, chunk_start + timedelta(days=1_400))
        response = request_get(
            FRED_OBSERVATIONS_URL,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start,
                "observation_end": end,
                "realtime_start": chunk_start.isoformat(),
                "realtime_end": chunk_end.isoformat(),
                "output_type": 4,
                "sort_order": "asc",
                "limit": 100000,
            },
            timeout=30,
        )
        if not getattr(response, "ok", True):
            try:
                message = response.json().get("error_message")
            except (AttributeError, ValueError):
                message = None
            raise RuntimeError(f"FRED rechazó {series_id} ({response.status_code}): {message or 'sin detalle'}")
        response.raise_for_status()
        rows.extend(parse_initial_releases(response.json()))
        chunk_start = chunk_end + timedelta(days=1)
    rows = list({(row["period"], row["release_at"]): row for row in rows}.values())
    rows.sort(key=lambda item: (item["period"], item["release_at"]))
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps({
            "series_id": series_id,
            "observation_start": start,
            "observation_end": end,
            "source": "FRED/ALFRED output_type=4",
            "observations": rows,
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    temporary.replace(path)
    return rows


def known_rows(rows: Iterable[dict[str, Any]], as_of: str | date | datetime) -> list[dict[str, Any]]:
    """Devuelve exclusivamente observaciones publicadas antes del corte."""
    cutoff = _day(as_of)
    return sorted(
        (
            row for row in rows
            if _day(row["period"]) <= cutoff and _day(row["release_at"]) <= cutoff
        ),
        key=lambda item: (_day(item["period"]), _day(item["release_at"])),
    )


def latest_value(rows: Iterable[dict[str, Any]], as_of: str | date | datetime) -> dict[str, Any] | None:
    visible = known_rows(rows, as_of)
    return visible[-1] if visible else None


def lagged_change(
    rows: Iterable[dict[str, Any]],
    as_of: str | date | datetime,
    *,
    periods: int,
    percent: bool,
) -> float | None:
    visible = known_rows(rows, as_of)
    if periods < 1 or len(visible) <= periods:
        return None
    latest = float(visible[-1]["value"])
    prior = float(visible[-1 - periods]["value"])
    if percent:
        return (latest / prior - 1) * 100 if prior else None
    return latest - prior
