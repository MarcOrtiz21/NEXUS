"""Gestión de snapshots compartidos para los endpoints del dashboard.

El motor de NEXUS es relativamente costoso: combina mercado, noticias,
calendario, historial y señales. Este servicio evita que varias peticiones
simultáneas repitan el mismo trabajo y mantiene una ventana corta de caché en
memoria para la UI.
"""

from __future__ import annotations

from threading import Lock
from time import monotonic
from typing import Any, Callable, Dict

from config import NATIVE_SNAPSHOT_TTL_SECONDS
from native_api import build_native_snapshot


class SnapshotService:
    """Caché TTL con single-flight: solo un consumidor recalcula a la vez."""

    def __init__(
        self,
        builder: Callable[..., Dict[str, Any]] = build_native_snapshot,
        ttl_seconds: int = NATIVE_SNAPSHOT_TTL_SECONDS,
    ) -> None:
        self._builder = builder
        self._ttl_seconds = max(0, int(ttl_seconds))
        self._lock = Lock()
        self._snapshot: Dict[str, Any] | None = None
        self._captured_monotonic = 0.0

    def _is_fresh(self) -> bool:
        return (
            self._snapshot is not None
            and monotonic() - self._captured_monotonic <= self._ttl_seconds
        )

    def get(self, *, force: bool = False, export: bool = False) -> Dict[str, Any]:
        """Devuelve el snapshot vigente o recalcula uno de forma exclusiva."""
        if not force and self._is_fresh():
            return self._snapshot  # type: ignore[return-value]

        wait = 0.2 if self._snapshot is not None else 25.0
        acquired = self._lock.acquire(timeout=wait)
        if not acquired:
            if self._snapshot is not None:
                return self._snapshot
            raise TimeoutError("El motor sigue calculando el snapshot. Reintenta en unos segundos.")

        try:
            if not force and self._is_fresh():
                return self._snapshot  # type: ignore[return-value]

            snapshot = self._builder(export=export)
            self._snapshot = snapshot
            self._captured_monotonic = monotonic()
            return snapshot
        finally:
            self._lock.release()

    def invalidate(self) -> None:
        """Fuerza la próxima lectura a recalcular el snapshot."""
        with self._lock:
            # Clear the cached payload. Zeroing the timestamp alone is unsafe:
            # on some hosts (CI containers) monotonic() starts near 0, so
            # captured=0.0 can still look "fresh" within the TTL window.
            self._snapshot = None
            self._captured_monotonic = 0.0


snapshot_service = SnapshotService()
