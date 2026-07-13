"""
Preferencias de usuario persistidas (sin terminal).

Se guardan en data/user_settings.json y pueden editarse desde la app desktop.
"""

from __future__ import annotations

import json
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


def _merge_defaults(raw: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = deepcopy(DEFAULTS)
    if raw:
        merged.update({k: v for k, v in raw.items() if k in DEFAULTS})
    if merged["calendar_block_hours"] not in (3, 6):
        merged["calendar_block_hours"] = DEFAULTS["calendar_block_hours"]
    merged["refresh_interval_seconds"] = max(60, min(3600, int(merged["refresh_interval_seconds"])))
    return merged


def load_user_settings(force: bool = False) -> Dict[str, Any]:
    global _settings_cache
    if _settings_cache is not None and not force:
        return _settings_cache

    raw: Dict[str, Any] | None = None
    if USER_SETTINGS_FILE.exists():
        try:
            raw = json.loads(USER_SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = None

    _settings_cache = _merge_defaults(raw)
    return _settings_cache


def get_setting(key: str) -> Any:
    settings = load_user_settings()
    return settings.get(key, DEFAULTS.get(key))


def save_user_settings(updates: Dict[str, Any]) -> Dict[str, Any]:
    global _settings_cache
    current = load_user_settings(force=True)
    current.update({k: v for k, v in updates.items() if k in DEFAULTS})
    merged = _merge_defaults(current)
    USER_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USER_SETTINGS_FILE.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    _settings_cache = merged
    return merged
