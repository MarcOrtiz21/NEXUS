"""
Notificaciones nativas de macOS para cambios de señal NEXUS.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from typing import Any, Dict, List, Tuple

from config import VIX_PANIC_THRESHOLD
from user_settings import get_setting

Notification = Tuple[str, str]


def notifications_enabled() -> bool:
    return sys.platform == "darwin" and bool(get_setting("macos_notifications"))


def send_macos_notification(title: str, message: str) -> bool:
    if not notifications_enabled():
        return False
    script = (
        f'display notification {json.dumps(message)} '
        f'with title {json.dumps(title)} subtitle "NEXUS"'
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            check=True,
            capture_output=True,
            text=True,
        )
        return True
    except Exception as exc:
        logging.warning(f"No se pudo enviar notificación macOS: {exc}")
        return False


def snapshot_state(snapshot: Dict[str, Any] | None) -> Dict[str, Any] | None:
    if not snapshot:
        return None
    decision = snapshot.get("decision") or {}
    data = snapshot.get("data") or {}
    vix = data.get("VIX")
    return {
        "status": snapshot.get("status"),
        "operational_action": decision.get("operational_action") or decision.get("action"),
        "macro_action": decision.get("macro_action") or decision.get("action"),
        "vix": float(vix) if vix is not None else None,
    }


def detect_notification_events(
    previous: Dict[str, Any] | None,
    current: Dict[str, Any],
) -> List[Notification]:
    if not previous:
        return []

    events: List[Notification] = []
    prev_ops = previous.get("operational_action")
    curr_ops = current.get("operational_action")
    prev_status = previous.get("status")
    curr_status = current.get("status")
    prev_vix = previous.get("vix")
    curr_vix = current.get("vix")
    prev_macro = previous.get("macro_action")
    curr_macro = current.get("macro_action")

    if prev_ops and curr_ops and prev_ops != curr_ops:
        events.append(("NEXUS — Señal operativa", f"{prev_ops} → {curr_ops}"))

    if curr_status in {"BLOCKED", "PANIC"} and curr_status != prev_status:
        if curr_status == "BLOCKED":
            events.append(("NEXUS — Pausa operativa", "Filtro de riesgo activo (calendario o sentimiento)."))
        else:
            events.append(("NEXUS — Pánico", "El motor detecta estrés extremo. Revisa liquidez y riesgo."))

    if curr_vix is not None and curr_vix >= VIX_PANIC_THRESHOLD and (prev_vix is None or prev_vix < VIX_PANIC_THRESHOLD):
        events.append(("NEXUS — VIX elevado", f"VIX en {curr_vix:.1f} (umbral {VIX_PANIC_THRESHOLD})."))

    if (
        curr_macro
        and curr_ops
        and curr_macro != curr_ops
        and (prev_macro == prev_ops or prev_macro != curr_macro)
    ):
        events.append((
            "NEXUS — Macro vs operativa",
            f"Macro {curr_macro}, operativa {curr_ops}.",
        ))

    return events


def notify_snapshot_change(
    previous_snapshot: Dict[str, Any] | None,
    current_snapshot: Dict[str, Any],
) -> int:
    previous = snapshot_state(previous_snapshot)
    current = snapshot_state(current_snapshot)
    if not current:
        return 0

    sent = 0
    for title, message in detect_notification_events(previous, current):
        if send_macos_notification(title, message):
            sent += 1
    return sent
