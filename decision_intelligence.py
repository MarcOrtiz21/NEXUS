"""Derived, explainable diagnostics used by the native decision interface."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _number(data: Dict[str, Any], key: str) -> float | None:
    value = data.get(key)
    return float(value) if isinstance(value, (int, float)) else None


def classify_market_regime(data: Dict[str, Any]) -> Dict[str, Any]:
    """Classify market context without treating it as an execution signal."""
    vix, vix_ma20 = _number(data, "VIX"), _number(data, "VIX_MA20")
    spy = (data.get("Assets") or {}).get("SPY") or {}
    momentum = spy.get("momentum_1m")
    price, ma50 = spy.get("price"), spy.get("ma50")
    if vix is not None and vix >= 28:
        regime, tone = "ESTRÉS", "bad"
    elif vix is not None and vix_ma20 and vix > vix_ma20 * 1.15:
        regime, tone = "CAUTELA", "warn"
    elif isinstance(momentum, (int, float)) and momentum > 0 and price and ma50 and price >= ma50:
        regime, tone = "EXPANSIÓN", "good"
    elif isinstance(momentum, (int, float)) and momentum < 0 and price and ma50 and price < ma50:
        regime, tone = "DESACELERACIÓN", "warn"
    else:
        regime, tone = "TRANSICIÓN", "neutral"
    return {
        "label": regime,
        "tone": tone,
        "vix": vix,
        "spy_momentum_1m": momentum,
        "summary": "Contexto descriptivo basado en volatilidad y tendencia; no sustituye la decisión operativa.",
    }


def score_attribution(data: Dict[str, Any], decision: Dict[str, Any]) -> Dict[str, Any]:
    """Explain observable inputs behind the score; weights are deliberately not invented."""
    assets = data.get("Assets") or {}
    spy = assets.get("SPY") or {}
    factors = [
        {"label": "Tendencia SPY", "value": spy.get("momentum_1m"), "unit": "% 1M"},
        {"label": "Volatilidad (VIX)", "value": data.get("VIX"), "unit": "nivel"},
        {"label": "Curva 10Y–2Y", "value": data.get("Yield_Curve_Spread"), "unit": "pp"},
        {"label": "Inflación", "value": data.get("CPI_YoY_Pct"), "unit": "%"},
    ]
    return {
        "score": decision.get("score"),
        "factors": [item for item in factors if item["value"] is not None],
        "note": "Muestra los factores observables disponibles; el score final incorpora reglas del motor.",
    }


def detect_market_anomalies(data: Dict[str, Any]) -> list[Dict[str, Any]]:
    checks = [
        ("VIX", _number(data, "VIX"), 28, "Volatilidad elevada"),
        ("VIX vs MA20", _ratio(data, "VIX", "VIX_MA20"), 0.15, "VIX muy por encima de su media"),
        ("Curva 10Y–2Y", _number(data, "Yield_Curve_Spread"), -0.25, "Curva invertida"),
        ("SPY momentum 1M", ((data.get("Assets") or {}).get("SPY") or {}).get("momentum_1m"), -5, "Caída mensual relevante"),
    ]
    anomalies = []
    for label, value, threshold, title in checks:
        if value is None:
            continue
        triggered = value >= threshold if label.startswith("VIX") else value <= threshold
        if triggered:
            anomalies.append({"label": label, "value": round(float(value), 2), "title": title, "severity": "warn"})
    return anomalies


def _ratio(data: Dict[str, Any], numerator: str, denominator: str) -> float | None:
    a, b = _number(data, numerator), _number(data, denominator)
    return (a / b - 1) if a is not None and b not in (None, 0) else None


def data_quality_summary(data: Dict[str, Any]) -> Dict[str, Any]:
    quality = data.get("DataQuality") or {}
    counts: Dict[str, int] = {}
    for item in quality.values():
        status = str((item or {}).get("status") or "UNKNOWN").upper()
        counts[status] = counts.get(status, 0) + 1
    unhealthy = sum(count for status, count in counts.items() if status not in {"OK", "FRESH"})
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(quality),
        "unhealthy": unhealthy,
        "status_counts": counts,
        "critical": [key for key, item in quality.items() if str((item or {}).get("status")).upper() in {"ERROR", "MISSING"}][:8],
    }
