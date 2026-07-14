"""
Preferencias de usuario persistidas (sin terminal).

Se guardan en data/user_settings.json y pueden editarse desde la app desktop.
"""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from config import DATA_DIR

USER_SETTINGS_FILE = DATA_DIR / "user_settings.json"

DEFAULTS: Dict[str, Any] = {
    "refresh_interval_seconds": 300,
    "calendar_block_hours": 6,
    "calendar_blocks_signals": True,
    "sentiment_blocks_signals": True,
    "use_finbert": False,
    "macos_notifications": True,
}

_settings_cache: Dict[str, Any] | None = None
_settings_lock = threading.Lock()


def _merge_defaults(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = deepcopy(DEFAULTS)
    if raw:
        merged.update({k: v for k, v in raw.items() if k in DEFAULTS})
    if merged["calendar_block_hours"] not in (3, 6):
        merged["calendar_block_hours"] = DEFAULTS["calendar_block_hours"]
    merged["refresh_interval_seconds"] = max(60, min(3600, int(merged["refresh_interval_seconds"])))
    return merged


def _read_settings_from_disk() -> Dict[str, Any]:
    raw: Dict[str, Any] | None = None
    if USER_SETTINGS_FILE.exists():
        try:
            raw = json.loads(USER_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = None
    return _merge_defaults(raw)


def load_user_settings(force: bool = False) -> Dict[str, Any]:
    global _settings_cache
    with _settings_lock:
        if _settings_cache is not None and not force:
            return _settings_cache

        _settings_cache = _read_settings_from_disk()
        return _settings_cache


def get_setting(key: str) -> Any:
    settings = load_user_settings()
    return settings.get(key, DEFAULTS.get(key))


def save_user_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    global _settings_cache
    with _settings_lock:
        current = _read_settings_from_disk()
        current.update({k: v for k, v in updates.items() if k in DEFAULTS})
        merged = _merge_defaults(current)
        USER_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = USER_SETTINGS_FILE.with_suffix('.tmp')
        tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.rename(USER_SETTINGS_FILE)
        _settings_cache = merged
        return merged
