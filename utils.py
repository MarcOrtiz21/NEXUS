"""
Utilidades compartidas de NEXUS.

Funciones comunes usadas por la CLI, la app desktop y otros módulos.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict


def now_utc_iso() -> str:
    """Timestamp UTC en formato ISO 8601."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_float(value: Any) -> float | None:
    """Conversión defensiva a float; devuelve None si falla."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def trend_label(metrics: Dict[str, Any]) -> str:
    """Etiqueta de tendencia basada en precio vs MA50/MA200."""
    price = metrics.get("price")
    ma50 = metrics.get("ma50")
    ma200 = metrics.get("ma200")
    if price is None or ma50 is None:
        return "sin datos"
    if ma200 is not None and price > ma50 > ma200:
        return "alcista"
    if ma200 is not None and price < ma50 < ma200:
        return "bajista"
    return "mixta"


def trend_from_metrics(metrics: Dict[str, Any]) -> str:
    """Tendencia basada en precio vs MA20 y MA50 (usada en forex)."""
    price = to_float(metrics.get("price"))
    ma20 = to_float(metrics.get("ma20"))
    ma50 = to_float(metrics.get("ma50"))
    if price is None or ma20 is None or ma50 is None:
        return "n/d"
    if price > ma20 > ma50:
        return "alcista"
    if price < ma20 < ma50:
        return "bajista"
    return "mixta"


def fmt(value, decimals: int = 2, suffix: str = "") -> str:
    """Formatea un valor numérico; devuelve '—' si es None."""
    if value is None:
        return "—"
    return f"{float(value):.{decimals}f}{suffix}"


def signed(value, decimals: int = 2, suffix: str = "%") -> str:
    """Formatea un valor numérico con signo; devuelve '—' si es None."""
    if value is None:
        return "—"
    return f"{float(value):+.{decimals}f}{suffix}"


def score_bar(score: int, width: int = 14) -> str:
    """Barra de progreso visual para scores 0-100."""
    score = max(0, min(100, int(score)))
    filled = round((score / 100.0) * width)
    return "█" * filled + "░" * (width - filled)


def metric_bar(value: float | None, low: float, high: float, width: int = 12) -> str:
    """Barra de gauge para un valor dentro de un rango."""
    if value is None:
        return "·" * width
    span = max(0.0001, high - low)
    pct = max(0.0, min(1.0, (float(value) - low) / span))
    filled = round(width * pct)
    return "█" * filled + "░" * (width - filled)


def build_snapshot(
    use_news: bool = True,
    export: bool = False,
) -> Dict[str, Any]:
    """
    Construye un snapshot completo de NEXUS.

    Fuente única de verdad para CLI, desktop y web dashboard.
    """
    from data_ingestion import fetch_market_data
    from logic_engine import LogicEngine
    from decision_engine import DecisionEngine
    from rotation_engine import RotationEngine
    from risk_filters.news_feed import fetch_news_items
    from history import export_decision_snapshot

    data = fetch_market_data()
    news_items = fetch_news_items() if use_news else []

    logic = LogicEngine(data, news_items=news_items if news_items else None)
    status, alerts = logic.evaluate()
    sentiment_result = getattr(logic, "sentiment_result", None)
    decision = DecisionEngine(data, status, alerts, sentiment_result=sentiment_result).evaluate()
    rotation = RotationEngine(data).evaluate()
    export_paths = (
        export_decision_snapshot(data, decision, news_items, market_status=status.value)
        if export
        else None
    )

    return {
        "captured_at_utc": now_utc_iso(),
        "status": status,
        "status_value": status.value,
        "alerts": alerts,
        "data": data,
        "decision": decision,
        "decision_dict": decision.to_dict(),
        "rotation": rotation,
        "rotation_dict": rotation.to_dict(),
        "calendar": getattr(logic, "calendar_result", {}),
        "news_items": news_items,
        "headlines": [item["title"] for item in news_items],
        "export_paths": export_paths,
    }


def snapshot_signature(snapshot: Dict[str, Any]) -> str:
    """Firma SHA-256 estable para detectar cambios en el snapshot."""
    data = snapshot["data"]
    # Soporta tanto objetos como dicts para decision/rotation
    decision = snapshot.get("decision_dict") or (
        snapshot["decision"].to_dict()
        if hasattr(snapshot.get("decision"), "to_dict")
        else snapshot.get("decision", {})
    )
    rotation = snapshot.get("rotation_dict") or (
        snapshot["rotation"].to_dict()
        if hasattr(snapshot.get("rotation"), "to_dict")
        else snapshot.get("rotation", {})
    )
    status = snapshot.get("status_value") or (
        snapshot["status"].value
        if hasattr(snapshot.get("status"), "value")
        else snapshot.get("status", "")
    )
    payload = {
        "status": status,
        "alerts": snapshot["alerts"],
        "decision": decision,
        "rotation": rotation,
        "market": {
            key: data.get(key)
            for key in (
                "VIX", "VIX_MA5", "VIX_MA10", "VIX_MA20", "US10Y",
                "Correlation_Proxy", "PE_Forward", "PE_Trailing",
                "M2_Change_Pct", "CPI_YoY_Pct",
            )
        },
        "forex": data.get("Forex", {}).get("EURUSD"),
        "usd_proxy": data.get("Assets", {}).get("UUP"),
        "news_titles": [item.get("title") for item in snapshot["news_items"][:30]],
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
