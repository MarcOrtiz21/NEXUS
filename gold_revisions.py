"""Diagnóstico de revisiones ALFRED, separado de las predicciones guardadas."""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from config import FRED_VINTAGE_CACHE_DIR
from fred_vintages import fetch_revision_history, first_release_rows, known_rows


REVISION_SERIES = {
    "CPIAUCSL": ("CPI general", "índice"),
    "CPILFESL": ("CPI subyacente", "índice"),
    "PCEPI": ("PCE general", "índice"),
    "PCEPILFE": ("PCE subyacente", "índice"),
    "CPIENGSL": ("CPI energético", "índice"),
    "UNRATE": ("Desempleo", "%"),
    "PAYEMS": ("Nóminas", "miles"),
    "INDPRO": ("Producción industrial", "índice"),
    "WM2NS": ("M2", "miles de millones USD"),
}


def revision_diagnostics(rows: list[dict[str, Any]], as_of: date, *, limit: int = 3) -> list[dict[str, Any]]:
    initial = {row["period"]: row for row in known_rows(first_release_rows(rows), as_of)}
    result = []
    for latest in known_rows(rows, as_of)[-limit:]:
        first = initial.get(latest["period"])
        if first is None:
            continue
        revisions = [row for row in rows if row["period"] == latest["period"]
                     and first["release_at"] < row["release_at"] <= as_of.isoformat()]
        result.append({"period": latest["period"], "initial_value": first["value"],
                       "known_value": latest["value"], "initial_release_at": first["release_at"],
                       "known_release_at": latest["release_at"],
                       "delta": round(latest["value"] - first["value"], 6),
                       "revision_count": len(revisions)})
    return result


def fetch_gold_revision_diagnostics(
    *, as_of: date | None = None, refresh: bool = False,
    cache_dir: Path = FRED_VINTAGE_CACHE_DIR,
    fetcher: Callable[..., list[dict[str, Any]]] = fetch_revision_history,
) -> dict[str, Any]:
    cutoff = as_of or datetime.now(timezone.utc).date()
    path = Path(cache_dir) / "gold_revision_diagnostics.json"
    cached = {}
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    usable = cached and str(cached.get("as_of") or "9999") <= cutoff.isoformat()
    if usable and cached.get("as_of") == cutoff.isoformat() and not refresh and time.time() - path.stat().st_mtime <= 86400:
        return cached
    previous = {item["series_id"]: item for item in cached.get("series") or []} if usable else {}
    start = (cutoff - timedelta(days=600)).isoformat()

    def load(entry):
        series_id, (label, unit) = entry
        try:
            rows = fetcher(series_id, start, cutoff.isoformat(), refresh=refresh, cache_dir=cache_dir)
            observations = revision_diagnostics(rows, cutoff)
            return {"series_id": series_id, "label": label, "unit": unit,
                    "status": "OK" if observations else "MISSING", "observations": observations}
        except Exception:
            old = previous.get(series_id)
            if old and old.get("observations"):
                return {**old, "status": "STALE", "note": "Consulta fallida; última comparación guardada."}
            return {"series_id": series_id, "label": label, "unit": unit,
                    "status": "MISSING", "observations": [], "note": "ALFRED no disponible para esta serie."}

    with ThreadPoolExecutor(max_workers=4) as executor:
        series = list(executor.map(load, REVISION_SERIES.items()))
    available = sum(item["status"] == "OK" for item in series)
    payload = {"as_of": cutoff.isoformat(), "generated_at": datetime.now(timezone.utc).isoformat(),
               "status": "OK" if available == len(series) else "PARTIAL" if available else "MISSING",
               "series": series, "score_enabled": False,
               "methodology": "Primera publicación frente a revisión conocida en el corte. Diferencias en la unidad original; no reescribe predicciones.",
               "date_precision": "day"}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return payload
