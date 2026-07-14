"""
Validación retrospectiva de señales NEXUS frente a SPY.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from config import normalize_action
from history_view import load_history_jsonl

BUY_ACTIONS = {"COMPRAR", "COMPRAR PARCIAL"}
DEFENSIVE_ACTIONS = {"ESPERAR", "REDUCIR RIESGO"}


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _action_label(row: Dict[str, Any], layer: str = "operational") -> str:
    if layer == "macro":
        raw = row.get("macro_action") or row.get("action") or "DESCONOCIDO"
    else:
        raw = row.get("operational_action") or row.get("action") or "DESCONOCIDO"
    return normalize_action(raw)


def _forward_return(rows: List[Dict[str, Any]], start_idx: int, forward_days: int) -> float | None:
    start = rows[start_idx]
    start_price = start.get("prices", {}).get("SPY")
    start_ts = _parse_ts(start.get("captured_at"))
    if start_price in (None, 0) or start_ts is None:
        return None

    target_ts = start_ts.timestamp() + forward_days * 86400
    best_idx = None
    best_delta = None
    for idx in range(start_idx + 1, len(rows)):
        later = rows[idx]
        later_ts = _parse_ts(later.get("captured_at"))
        later_price = later.get("prices", {}).get("SPY")
        if later_ts is None or later_price in (None, 0):
            continue
        delta = abs(later_ts.timestamp() - target_ts)
        if later_ts.timestamp() < start_ts.timestamp():
            continue
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_idx = idx

    if best_idx is None:
        return None

    end_price = rows[best_idx]["prices"]["SPY"]
    return round(((end_price / start_price) - 1) * 100, 2)


def evaluate_track_record(forward_days: int = 5, limit: int | None = None) -> Dict[str, Any]:
    rows = load_history_jsonl(limit=limit)
    if len(rows) < 2:
        return {
            "sample_size": 0,
            "forward_days": forward_days,
            "message": "Historial insuficiente para calcular track record.",
        }

    evaluated: List[Dict[str, Any]] = []
    for idx in range(len(rows) - 1):
        fwd = _forward_return(rows, idx, forward_days)
        if fwd is None:
            continue
        row = rows[idx]
        macro_action = _action_label(row, "macro")
        operational_action = _action_label(row, "operational")
        evaluated.append({
            "captured_at": row.get("captured_at"),
            "macro_action": macro_action,
            "operational_action": operational_action,
            "score": row.get("score"),
            "spy_forward_return_pct": fwd,
            "macro_correct": macro_action in BUY_ACTIONS and fwd > 0,
            "defensive_correct": operational_action in DEFENSIVE_ACTIONS and fwd <= 0,
        })

    if not evaluated:
        return {
            "sample_size": 0,
            "forward_days": forward_days,
            "message": "No hay suficientes snapshots separados para medir retornos forward.",
        }

    buy_macro = [item for item in evaluated if item["macro_action"] in BUY_ACTIONS]
    defensive_ops = [item for item in evaluated if item["operational_action"] in DEFENSIVE_ACTIONS]

    def _avg(items: List[Dict[str, Any]], key: str = "spy_forward_return_pct") -> float | None:
        values = [item[key] for item in items]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    def _hit_rate(items: List[Dict[str, Any]], flag: str) -> float | None:
        if not items:
            return None
        return round(sum(1 for item in items if item[flag]) / len(items) * 100, 1)

    return {
        "sample_size": len(evaluated),
        "forward_days": forward_days,
        "macro_buy_count": len(buy_macro),
        "macro_buy_avg_return_pct": _avg(buy_macro),
        "macro_buy_hit_rate_pct": _hit_rate(buy_macro, "macro_correct"),
        "defensive_count": len(defensive_ops),
        "defensive_avg_return_pct": _avg(defensive_ops),
        "defensive_hit_rate_pct": _hit_rate(defensive_ops, "defensive_correct"),
        "overall_avg_return_pct": _avg(evaluated),
        "recent_samples": evaluated[-5:],
    }


def format_track_record_report(forward_days: int = 5, limit: int | None = 100) -> str:
    summary = evaluate_track_record(forward_days=forward_days, limit=limit)
    if summary.get("sample_size", 0) == 0:
        return summary.get("message", "Sin datos de track record.")

    lines = [
        f"TRACK RECORD NEXUS vs SPY ({summary['forward_days']} días forward)",
        f"Muestras evaluadas: {summary['sample_size']}",
        "",
        "DIAGNÓSTICO MACRO (COMPRAR / COMPRAR PARCIAL)",
        f"  Señales: {summary['macro_buy_count']}",
        f"  Retorno medio SPY: {summary['macro_buy_avg_return_pct']:+.2f}%"
        if summary["macro_buy_avg_return_pct"] is not None else "  Retorno medio SPY: —",
        f"  Acierto (SPY > 0): {summary['macro_buy_hit_rate_pct']}%"
        if summary["macro_buy_hit_rate_pct"] is not None else "  Acierto: —",
        "",
        "SEÑAL OPERATIVA DEFENSIVA (ESPERAR / REDUCIR RIESGO)",
        f"  Señales: {summary['defensive_count']}",
        f"  Retorno medio SPY: {summary['defensive_avg_return_pct']:+.2f}%"
        if summary["defensive_avg_return_pct"] is not None else "  Retorno medio SPY: —",
        f"  Acierto (SPY <= 0): {summary['defensive_hit_rate_pct']}%"
        if summary["defensive_hit_rate_pct"] is not None else "  Acierto: —",
        "",
        "ÚLTIMAS MUESTRAS",
    ]
    for sample in summary.get("recent_samples", []):
        lines.append(
            f"  {sample['captured_at']}  macro={sample['macro_action']}  "
            f"ops={sample['operational_action']}  SPY {sample['spy_forward_return_pct']:+.2f}%"
        )
    return "\n".join(lines)
