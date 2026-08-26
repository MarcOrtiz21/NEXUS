"""
Validación retrospectiva de señales NEXUS frente a SPY.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from config import (
    HISTORY_CALIBRATION_MIN_SAMPLES,
    VIX_CALM_THRESHOLD,
    VIX_ELEVATED_THRESHOLD,
    VIX_PANIC_THRESHOLD,
    normalize_action,
)
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
    max_gap_seconds = max(3 * 86400, int(forward_days * 0.2 * 86400))
    for idx in range(start_idx + 1, len(rows)):
        later = rows[idx]
        later_ts = _parse_ts(later.get("captured_at"))
        later_price = later.get("prices", {}).get("SPY")
        if later_ts is None or later_price in (None, 0):
            continue
        delta = later_ts.timestamp() - target_ts
        if delta < 0 or later_ts.timestamp() < start_ts.timestamp():
            continue
        if delta > max_gap_seconds:
            continue
        if best_delta is None or delta < best_delta:
            best_delta = delta
            best_idx = idx

    if best_idx is None:
        return None

    end_price = rows[best_idx]["prices"]["SPY"]
    return round(((end_price / start_price) - 1) * 100, 2)


def _vix_bucket(vix: Any) -> str | None:
    if not isinstance(vix, (int, float)):
        return None
    if vix >= VIX_PANIC_THRESHOLD:
        return "estres"
    if vix >= VIX_ELEVATED_THRESHOLD:
        return "cautela"
    if vix < VIX_CALM_THRESHOLD:
        return "calma"
    return "normal"


def _vix_bucket_stats(samples: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for item in samples:
        if item.get("macro_action") not in BUY_ACTIONS:
            continue
        bucket = _vix_bucket(item.get("vix"))
        if bucket is None:
            continue
        grouped.setdefault(bucket, []).append(item)
    stats: Dict[str, Dict[str, Any]] = {}
    for name, items in grouped.items():
        hits = sum(1 for item in items if item.get("macro_correct"))
        stats[name] = {
            "count": len(items),
            "hit_rate_pct": round(hits / len(items) * 100, 1) if items else None,
        }
    return stats


def _horizon_public(summary: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "forward_days": summary.get("forward_days"),
        "sample_size": summary.get("sample_size"),
        "macro_buy_count": summary.get("macro_buy_count"),
        "macro_buy_hit_rate_pct": summary.get("macro_buy_hit_rate_pct"),
        "macro_buy_avg_return_pct": summary.get("macro_buy_avg_return_pct"),
        "defensive_count": summary.get("defensive_count"),
        "defensive_hit_rate_pct": summary.get("defensive_hit_rate_pct"),
    }


def _summarize_horizon(rows: List[Dict[str, Any]], forward_days: int) -> Dict[str, Any]:
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
            "vix": row.get("vix"),
            "spy_forward_return_pct": fwd,
            "macro_correct": macro_action in BUY_ACTIONS and fwd > 0,
            "defensive_correct": operational_action in DEFENSIVE_ACTIONS and fwd <= 0,
        })

    if not evaluated:
        return {
            "sample_size": 0,
            "forward_days": forward_days,
            "macro_buy_count": 0,
            "macro_buy_avg_return_pct": None,
            "macro_buy_hit_rate_pct": None,
            "defensive_count": 0,
            "defensive_avg_return_pct": None,
            "defensive_hit_rate_pct": None,
            "overall_avg_return_pct": None,
            "samples": [],
            "recent_samples": [],
            "by_operational_signal": {},
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

    by_signal: Dict[str, Dict[str, Any]] = {}
    for item in evaluated:
        label = item["operational_action"]
        bucket = by_signal.setdefault(label, {"count": 0, "returns": []})
        bucket["count"] += 1
        bucket["returns"].append(item["spy_forward_return_pct"])
    for bucket in by_signal.values():
        returns = bucket.pop("returns")
        bucket["avg_return_pct"] = round(sum(returns) / len(returns), 2) if returns else None
        bucket["hit_rate_pct"] = round(sum(1 for value in returns if value > 0) / len(returns) * 100, 1) if returns else None

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
        "samples": evaluated,
        "recent_samples": evaluated[-5:],
        "by_operational_signal": by_signal,
    }


def evaluate_track_record(
    forward_days: int = 5,
    limit: int | None = None,
    extra_horizons: tuple[int, ...] = (20,),
) -> Dict[str, Any]:
    rows = load_history_jsonl(limit=limit)
    if len(rows) < 2:
        return {
            "sample_size": 0,
            "forward_days": forward_days,
            "macro_buy_count": 0,
            "macro_buy_count_20d": 0,
            "macro_buy_hit_rate_20d_pct": None,
            "vix_buckets": {},
            "message": "Historial insuficiente para calcular track record.",
        }

    primary = _summarize_horizon(rows, forward_days)
    extra = {horizon: _summarize_horizon(rows, horizon) for horizon in extra_horizons}
    h20 = extra.get(20) or {}
    if primary.get("sample_size", 0) == 0:
        primary["macro_buy_count_20d"] = h20.get("macro_buy_count") or 0
        primary["macro_buy_hit_rate_20d_pct"] = h20.get("macro_buy_hit_rate_pct")
        primary["macro_buy_avg_return_20d_pct"] = h20.get("macro_buy_avg_return_pct")
        primary["vix_buckets"] = {}
        return primary

    primary["macro_buy_count_20d"] = h20.get("macro_buy_count") or 0
    primary["macro_buy_hit_rate_20d_pct"] = h20.get("macro_buy_hit_rate_pct")
    primary["macro_buy_avg_return_20d_pct"] = h20.get("macro_buy_avg_return_pct")
    primary["forward_horizons"] = {
        forward_days: _horizon_public(primary),
        **{horizon: _horizon_public(summary) for horizon, summary in extra.items()},
    }
    primary["vix_buckets"] = _vix_bucket_stats(primary.get("samples") or [])
    return primary


def history_buy_scale(
    track: Dict[str, Any] | None,
    min_samples: int | None = None,
) -> tuple[float, str | None]:
    """Escala el sesgo alcista según acierto COMPRAR vs SPY. No reescribe umbrales VIX."""
    track = track or {}
    floor = min_samples if min_samples is not None else HISTORY_CALIBRATION_MIN_SAMPLES
    count = int(track.get("macro_buy_count") or 0)
    hit = track.get("macro_buy_hit_rate_pct")
    if count < floor or not isinstance(hit, (int, float)):
        return 1.0, None
    effective = float(hit)
    count20 = int(track.get("macro_buy_count_20d") or 0)
    hit20 = track.get("macro_buy_hit_rate_20d_pct")
    if count20 >= floor and isinstance(hit20, (int, float)):
        effective = min(effective, float(hit20))
    if effective >= 55:
        return 1.0, None
    if effective >= 40:
        return 0.85, "la muestra reciente de COMPRAR apenas confirma el sentido de SPY"
    return 0.7, "la muestra reciente de COMPRAR no confirma el sentido de SPY frente al índice"


def track_record_chart_payload(
    forward_days: int = 5,
    limit: int | None = 100,
    chart_limit: int = 40,
) -> Dict[str, Any]:
    """Datos listos para dibujar hit-rates y barras de retorno forward."""
    summary = evaluate_track_record(forward_days=forward_days, limit=limit)
    samples = summary.get("samples") or []
    chart_samples = samples[-chart_limit:]
    hit_bars = [
        {
            "label": "Macro COMPRAR",
            "value": summary.get("macro_buy_hit_rate_pct"),
            "count": summary.get("macro_buy_count", 0),
            "color": "good",
        },
        {
            "label": "Ops DEFENSIVA",
            "value": summary.get("defensive_hit_rate_pct"),
            "count": summary.get("defensive_count", 0),
            "color": "warn",
        },
    ]
    if int(summary.get("macro_buy_count_20d") or 0) > 0:
        hit_bars.append({
            "label": "Macro COMPRAR 20d",
            "value": summary.get("macro_buy_hit_rate_20d_pct"),
            "count": summary.get("macro_buy_count_20d", 0),
            "color": "good",
        })
    return {
        **summary,
        "chart_samples": chart_samples,
        "hit_bars": hit_bars,
    }


def format_track_record_report(forward_days: int = 5, limit: int | None = 100) -> str:
    summary = evaluate_track_record(forward_days=forward_days, limit=limit)
    if summary.get("sample_size", 0) == 0:
        return summary.get("message", "Sin datos de track record.")

    buy_avg = summary.get("macro_buy_avg_return_pct")
    buy_hit = summary.get("macro_buy_hit_rate_pct")
    buy_hit_20 = summary.get("macro_buy_hit_rate_20d_pct")
    def_avg = summary.get("defensive_avg_return_pct")
    def_hit = summary.get("defensive_hit_rate_pct")
    lines = [
        f"TRACK RECORD NEXUS vs SPY ({summary['forward_days']} días forward)",
        f"Muestras evaluadas: {summary['sample_size']}",
        "",
        "DIAGNÓSTICO MACRO (COMPRAR / COMPRAR PARCIAL)",
        f"  Señales: {summary['macro_buy_count']}",
        f"  Retorno medio SPY: {buy_avg:+.2f}%" if buy_avg is not None else "  Retorno medio SPY: —",
        f"  Acierto (SPY > 0): {buy_hit}%" if buy_hit is not None else "  Acierto: —",
    ]
    if int(summary.get("macro_buy_count_20d") or 0) > 0:
        lines.append(f"  Acierto 20d: {buy_hit_20}%" if buy_hit_20 is not None else "  Acierto 20d: —")
    lines.extend([
        "",
        "SEÑAL OPERATIVA DEFENSIVA (ESPERAR / REDUCIR RIESGO)",
        f"  Señales: {summary['defensive_count']}",
        f"  Retorno medio SPY: {def_avg:+.2f}%" if def_avg is not None else "  Retorno medio SPY: —",
        f"  Acierto (SPY <= 0): {def_hit}%" if def_hit is not None else "  Acierto: —",
        "",
        "ÚLTIMAS MUESTRAS",
    ])
    for sample in summary.get("recent_samples", []):
        lines.append(
            f"  {sample['captured_at']}  macro={sample['macro_action']}  "
            f"ops={sample['operational_action']}  SPY {sample['spy_forward_return_pct']:+.2f}%"
        )
    return "\n".join(lines)
