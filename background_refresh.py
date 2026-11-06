"""Actualización programada de NEXUS sin depender de que la app esté abierta.

Si el motor de la app escucha en :8765 se le pide el refresco (así la app
recibe el snapshot nuevo); si no, se construye y persiste aquí mismo.
"""

from __future__ import annotations

import fcntl
import logging
import sys
from contextlib import contextmanager
from typing import Iterator

import requests

from config import CACHE_DIR

ENGINE_URL = "http://127.0.0.1:8765"
REFRESH_TIMEOUT_SECONDS = 600
LOCK_FILE = CACHE_DIR / ".background_refresh.lock"


@contextmanager
def single_run() -> Iterator[bool]:
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK_FILE, "w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def engine_alive(session=requests) -> bool:
    try:
        return session.get(f"{ENGINE_URL}/api/health", timeout=3).status_code == 200
    except requests.RequestException:
        return False


def refresh_via_engine(session=requests) -> str:
    response = session.post(f"{ENGINE_URL}/api/native/refresh", timeout=REFRESH_TIMEOUT_SECONDS)
    response.raise_for_status()
    return str(response.json().get("captured_at_utc") or "")


def refresh_headless() -> str:
    from native_api import build_native_snapshot

    return str(build_native_snapshot(export=True).get("captured_at_utc") or "")


def run(session=requests) -> int:
    with single_run() as acquired:
        if not acquired:
            logging.info("Otra actualización programada sigue en curso; se omite.")
            return 0
        try:
            if engine_alive(session):
                captured = refresh_via_engine(session)
                logging.info("Actualizado vía motor de la app · captura %s", captured)
            else:
                captured = refresh_headless()
                logging.info("Actualizado sin app · captura %s", captured)
            return 0
        except Exception:
            logging.exception("Falló la actualización programada")
            return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    sys.exit(run())
