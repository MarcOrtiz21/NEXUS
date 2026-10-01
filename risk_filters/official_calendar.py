"""Calendarios oficiales de decisiones de bancos centrales con caché degradable.

Las fechas se descargan de la página oficial y se guardan en caché local; si
la página no responde se usa la caché aunque esté caducada y no se reintenta
hasta pasado un intervalo.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List

import requests

_RETRY_AFTER = timedelta(minutes=15)


class OfficialDecisionCalendar:
    def __init__(
        self,
        *,
        source: str,
        url: str,
        cache_path: Path,
        ttl_seconds: int,
        parser: Callable[[str], List[date]],
    ) -> None:
        self.source = source
        self.url = url
        self.cache_path = cache_path
        self.ttl_seconds = ttl_seconds
        self.parser = parser
        self._memory: Dict[str, Any] | None = None
        self._last_failure: datetime | None = None

    def clear(self) -> None:
        self._memory = None
        self._last_failure = None

    def _fresh(self, payload: Dict[str, Any] | None, now: datetime) -> bool:
        try:
            captured = datetime.fromisoformat(str((payload or {}).get("captured_at")))
        except ValueError:
            return False
        return (now - captured).total_seconds() <= self.ttl_seconds

    @staticmethod
    def _read(path: Path) -> Dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or not isinstance(payload.get("decisions"), list):
            return None
        return payload

    def _write(self, path: Path, payload: Dict[str, Any]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        except OSError as exc:
            logging.warning(f"No se pudo guardar caché {self.source}: {exc}")

    @staticmethod
    def _dates(payload: Dict[str, Any] | None) -> List[date]:
        return [date.fromisoformat(value) for value in (payload or {}).get("decisions", [])]

    def decision_dates(
        self,
        now: datetime,
        *,
        cache_path: Path | None = None,
        session: Any = None,
    ) -> List[date]:
        path = cache_path or self.cache_path
        if self._memory and self._fresh(self._memory, now):
            return self._dates(self._memory)
        disk = self._read(path)
        if disk and self._fresh(disk, now):
            self._memory = disk
            return self._dates(disk)
        if self._last_failure is not None and now - self._last_failure < _RETRY_AFTER:
            return self._dates(disk)

        try:
            response = (session or requests).get(
                self.url, timeout=10,
                headers={"User-Agent": "NEXUS/1.0 (+local workstation)"},
            )
            response.raise_for_status()
            decisions = self.parser(response.text)
            if not decisions:
                raise ValueError("la página no contiene reuniones reconocibles")
        except Exception as exc:
            logging.warning(f"Error al leer calendario {self.source}: {exc}")
            self._last_failure = now
            return self._dates(disk)

        payload = {
            "source": self.source,
            "url": self.url,
            "captured_at": now.isoformat(timespec="seconds"),
            "decisions": [day.isoformat() for day in decisions],
        }
        self._write(path, payload)
        self._memory = payload
        self._last_failure = None
        return decisions
