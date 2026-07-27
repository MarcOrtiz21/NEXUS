"""
Consulta del historial de decisiones NEXUS.
"""

from __future__ import annotations

import csv
import json
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

from config import DECISIONS_HISTORY_CSV, DECISIONS_HISTORY_JSONL

SUPPORTED_PERIODS = {"7d": 7, "30d": 30, "90d": 90}
DEFAULT_MAX_POINTS = 120


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def load_history_jsonl(path: Path = DECISIONS_HISTORY_JSONL, limit: int | None = None) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if limit is not None:
        return rows[-limit:]
    return rows


def load_history_period(
    period: str = "30d",
    path: Path = DECISIONS_HISTORY_JSONL,
) -> List[Dict[str, Any]]:
    """Carga 7/30/90 días en una pasada y con memoria acotada al periodo."""
    days = SUPPORTED_PERIODS.get(period)
    if days is None:
        raise ValueError(f"Periodo no soportado: {period}. Usa 7d, 30d o 90d.")
    if not path.exists():
        return []

    rows: deque[tuple[datetime, Dict[str, Any]]] = deque()
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            try:
                row = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            captured = _parse_timestamp(row.get("captured_at"))
            if captured is None:
                continue
            rows.append((captured, row))
            cutoff = captured - timedelta(days=days)
            while rows and rows[0][0] < cutoff:
                rows.popleft()
    return [row for _, row in rows]


def filter_history_period(rows: List[Dict[str, Any]], period: str) -> List[Dict[str, Any]]:
    """Recorta filas ya cargadas usando el snapshot más reciente como ancla."""
    days = SUPPORTED_PERIODS.get(period)
    if days is None:
        raise ValueError(f"Periodo no soportado: {period}. Usa 7d, 30d o 90d.")
    dated = [(stamp, row) for row in rows if (stamp := _parse_timestamp(row.get("captured_at"))) is not None]
    if not dated:
        return []
    cutoff = dated[-1][0] - timedelta(days=days)
    return [row for stamp, row in dated if stamp >= cutoff]


def downsample_rows(rows: List[Dict[str, Any]], max_points: int = DEFAULT_MAX_POINTS) -> List[Dict[str, Any]]:
    """Muestreo uniforme determinista que siempre conserva extremos."""
    if max_points < 2:
        raise ValueError("max_points debe ser al menos 2")
    if len(rows) <= max_points:
        return list(rows)
    last = len(rows) - 1
    indexes = [round(index * last / (max_points - 1)) for index in range(max_points)]
    return [rows[index] for index in indexes]


def load_history_csv(path: Path = DECISIONS_HISTORY_CSV, limit: int | None = None) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if limit is not None:
        return rows[-limit:]
    return rows


def summarize_history(
    limit: int = 30,
    *,
    period: str | None = None,
    max_points: int = DEFAULT_MAX_POINTS,
    path: Path = DECISIONS_HISTORY_JSONL,
    rows: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    if rows is None:
        rows = load_history_period(period, path=path) if period else load_history_jsonl(path=path, limit=limit)
    if not rows:
        return {
            "count": 0,
            "latest": None,
            "score_timeline": [],
            "action_changes": [],
            "action_counts": {},
            "period": period,
            "source_count": 0,
            "asset_ranking": [],
        }

    source_count = len(rows)
    timeline_rows = downsample_rows(rows, max_points=max_points)
    score_timeline = [
        {
            "captured_at": row.get("captured_at"),
            "score": row.get("score"),
            "action": row.get("operational_action") or row.get("action"),
            "macro_action": row.get("macro_action") or row.get("action"),
            "operational_action": row.get("operational_action") or row.get("action"),
        }
        for row in timeline_rows
    ]

    action_changes = []
    previous_action = None
    for row in rows:
        action = row.get("action")
        if previous_action and action != previous_action:
            action_changes.append({
                "captured_at": row.get("captured_at"),
                "from": previous_action,
                "to": action,
                "score": row.get("score"),
            })
        previous_action = action

    action_counts: Dict[str, int] = {}
    for row in rows:
        action = row.get("action", "DESCONOCIDO")
        action_counts[action] = action_counts.get(action, 0) + 1

    scores = [row.get("score") for row in rows if isinstance(row.get("score"), (int, float))]
    comparison = compare_to_prior(rows)
    return {
        "count": len(rows),
        "source_count": source_count,
        "period": period,
        "max_points": max_points,
        "downsampled": source_count > len(timeline_rows),
        "latest": rows[-1],
        "score_timeline": score_timeline,
        "action_changes": action_changes,
        "action_counts": action_counts,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
        "events": action_changes[-40:],
        "price_series": build_price_series(timeline_rows),
        "comparison": comparison,
        "asset_ranking": comparison.get("asset_ranking", []),
    }


def build_price_series(rows: List[Dict[str, Any]] | None = None, limit: int = 120) -> Dict[str, List[Dict[str, Any]]]:
    """Series históricas de precios (SPY, GLD, UUP, EURUSD) desde JSONL."""
    if rows is None:
        rows = load_history_jsonl(limit=limit)
    series: Dict[str, List[Dict[str, Any]]] = {
        "SPY": [],
        "GLD": [],
        "UUP": [],
        "QQQ": [],
        "TLT": [],
        "EURUSD": [],
        "score": [],
    }
    for row in rows:
        captured = row.get("captured_at")
        prices = row.get("prices") or {}
        for key in ("SPY", "GLD", "UUP", "QQQ", "TLT", "EURUSD"):
            value = prices.get(key)
            if value is None:
                continue
            try:
                series[key].append({"captured_at": captured, "value": float(value)})
            except (TypeError, ValueError):
                continue
        score = row.get("score")
        if isinstance(score, (int, float)):
            series["score"].append({"captured_at": captured, "value": float(score)})
    return series


def compare_to_prior(rows: List[Dict[str, Any]] | None = None, limit: int = 120) -> Dict[str, Any]:
    """Comparativa vs snapshot anterior y vs último del día previo si existe."""
    if rows is None:
        rows = load_history_jsonl(limit=limit)
    if len(rows) < 2:
        latest = rows[-1] if rows else None
        return {
            "has_prior": False,
            "latest": latest,
            "prior": None,
            "vs_previous": None,
            "vs_yesterday": None,
            "asset_ranking": build_asset_ranking(latest, None) if latest else [],
            "attribution": None,
        }

    latest = rows[-1]
    prior = rows[-2]
    vs_previous = _diff_rows(latest, prior)

    yesterday = None
    latest_day = _day_key(latest.get("captured_at"))
    for row in reversed(rows[:-1]):
        if _day_key(row.get("captured_at")) != latest_day:
            yesterday = row
            break
    vs_yesterday = _diff_rows(latest, yesterday) if yesterday else None

    return {
        "has_prior": True,
        "latest_captured_at": latest.get("captured_at"),
        "prior_captured_at": prior.get("captured_at"),
        "yesterday_captured_at": (yesterday or {}).get("captured_at"),
        "vs_previous": vs_previous,
        "vs_yesterday": vs_yesterday,
        "asset_ranking": vs_previous["asset_ranking"],
        "attribution": vs_previous["attribution"],
    }


def _day_key(value: Any) -> str | None:
    if not value:
        return None
    text = str(value)
    return text[:10] if len(text) >= 10 else text


def _pct_delta(current: Any, previous: Any) -> float | None:
    try:
        cur = float(current)
        prev = float(previous)
    except (TypeError, ValueError):
        return None
    if prev == 0:
        return None
    return round(((cur - prev) / prev) * 100.0, 3)


def _numeric_score(metrics: Any) -> float | None:
    if not isinstance(metrics, dict):
        return None
    score = metrics.get("score")
    return float(score) if isinstance(score, (int, float)) else None


def build_asset_ranking(
    current: Dict[str, Any] | None,
    previous: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    """Ranking y deltas por ticker a partir de asset_scores persistidos."""
    current_scores = (current or {}).get("asset_scores") or {}
    previous_scores = (previous or {}).get("asset_scores") or {}
    current_order = sorted(current_scores, key=lambda ticker: _numeric_score(current_scores[ticker]) or -1, reverse=True)
    previous_order = sorted(previous_scores, key=lambda ticker: _numeric_score(previous_scores[ticker]) or -1, reverse=True)
    previous_ranks = {ticker: index + 1 for index, ticker in enumerate(previous_order)}
    ranking = []
    for index, ticker in enumerate(current_order):
        metrics = current_scores.get(ticker) or {}
        score = _numeric_score(metrics)
        prior_score = _numeric_score(previous_scores.get(ticker))
        rank = index + 1
        prior_rank = previous_ranks.get(ticker)
        ranking.append({
            "ticker": ticker,
            "label": metrics.get("label") or ticker,
            "score": score,
            "prior_score": prior_score,
            "score_delta": round(score - prior_score, 1) if score is not None and prior_score is not None else None,
            "rank": rank,
            "prior_rank": prior_rank,
            "rank_delta": prior_rank - rank if prior_rank is not None else None,
            "action": metrics.get("action"),
        })
    return ranking


def _diff_rows(current: Dict[str, Any], previous: Dict[str, Any]) -> Dict[str, Any]:
    cur_prices = current.get("prices") or {}
    prev_prices = previous.get("prices") or {}
    cur_action = current.get("operational_action") or current.get("action")
    prev_action = previous.get("operational_action") or previous.get("action")
    cur_score = current.get("score")
    prev_score = previous.get("score")
    score_delta = None
    if isinstance(cur_score, (int, float)) and isinstance(prev_score, (int, float)):
        score_delta = round(float(cur_score) - float(prev_score), 1)
    asset_ranking = build_asset_ranking(current, previous)
    movers = sorted(
        (item for item in asset_ranking if item["score_delta"] is not None),
        key=lambda item: abs(item["score_delta"]),
        reverse=True,
    )[:3]
    market_from = previous.get("market_status")
    market_to = current.get("market_status")
    rationale_from = previous.get("rationale")
    rationale_to = current.get("rationale")
    attribution = {
        "score": {"from": prev_score, "to": cur_score, "delta": score_delta},
        "action": {"from": prev_action, "to": cur_action, "changed": cur_action != prev_action},
        "market_status": {"from": market_from, "to": market_to, "changed": market_from != market_to},
        "top_asset_movers": movers,
        "rationale": {
            "from": rationale_from,
            "to": rationale_to,
            "changed": rationale_from != rationale_to,
        },
        "note": "Atribución descriptiva entre snapshots; no implica causalidad.",
    }
    return {
        "score_delta": score_delta,
        "action_from": prev_action,
        "action_to": cur_action,
        "action_changed": cur_action != prev_action,
        "market_status_from": market_from,
        "market_status_to": market_to,
        "spy_pct": _pct_delta(cur_prices.get("SPY"), prev_prices.get("SPY")),
        "gld_pct": _pct_delta(cur_prices.get("GLD"), prev_prices.get("GLD")),
        "uup_pct": _pct_delta(cur_prices.get("UUP"), prev_prices.get("UUP")),
        "eurusd_pct": _pct_delta(cur_prices.get("EURUSD"), prev_prices.get("EURUSD")),
        "previous_captured_at": previous.get("captured_at"),
        "asset_ranking": asset_ranking,
        "top_asset_movers": movers,
        "attribution": attribution,
    }


def format_history_report(limit: int = 20) -> str:
    summary = summarize_history(limit=limit)
    if summary["count"] == 0:
        return "No hay historial de decisiones todavía. Ejecuta NEXUS con exportación activa."

    lines = [
        f"HISTORIAL NEXUS ({summary['count']} snapshots)",
        f"Score medio: {summary['avg_score']} | Min: {summary['min_score']} | Max: {summary['max_score']}",
        "",
        "EVOLUCIÓN RECIENTE",
    ]
    for point in summary["score_timeline"][-10:]:
        macro = point.get("macro_action") or point.get("action")
        operational = point.get("operational_action") or point.get("action")
        if macro != operational:
            lines.append(
                f"  {point['captured_at']}  score={point['score']}  macro={macro}  ops={operational}"
            )
        else:
            lines.append(f"  {point['captured_at']}  score={point['score']}  action={operational}")

    lines.extend(["", "CAMBIOS DE SEÑAL"])
    if summary["action_changes"]:
        for change in summary["action_changes"][-8:]:
            lines.append(
                f"  {change['captured_at']}  {change['from']} -> {change['to']}  (score {change['score']})"
            )
    else:
        lines.append("  Sin cambios de acción en el periodo consultado.")

    lines.extend(["", "DISTRIBUCIÓN DE ACCIONES"])
    for action, count in sorted(summary["action_counts"].items(), key=lambda item: item[1], reverse=True):
        lines.append(f"  {action}: {count}")

    latest = summary["latest"] or {}
    lines.extend([
        "",
        "ÚLTIMA DECISIÓN",
        f"  Macro: {latest.get('macro_action') or latest.get('action')}",
        f"  Operativa: {latest.get('operational_action') or latest.get('action')}",
        f"  Score: {latest.get('score')}",
        f"  Confianza: {latest.get('confidence')}",
        f"  Favorecidos: {', '.join(latest.get('favored_assets', []))}",
    ])
    return "\n".join(lines)
