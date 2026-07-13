"""
Consulta del historial de decisiones NEXUS.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from config import DECISIONS_HISTORY_CSV, DECISIONS_HISTORY_JSONL


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


def load_history_csv(path: Path = DECISIONS_HISTORY_CSV, limit: int | None = None) -> List[Dict[str, Any]]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if limit is not None:
        return rows[-limit:]
    return rows


def summarize_history(limit: int = 30) -> Dict[str, Any]:
    rows = load_history_jsonl(limit=limit)
    if not rows:
        return {
            "count": 0,
            "latest": None,
            "score_timeline": [],
            "action_changes": [],
            "action_counts": {},
        }

    score_timeline = [
        {
            "captured_at": row.get("captured_at"),
            "score": row.get("score"),
            "action": row.get("operational_action") or row.get("action"),
            "macro_action": row.get("macro_action") or row.get("action"),
            "operational_action": row.get("operational_action") or row.get("action"),
        }
        for row in rows
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
    return {
        "count": len(rows),
        "latest": rows[-1],
        "score_timeline": score_timeline,
        "action_changes": action_changes,
        "action_counts": action_counts,
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
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
