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
    "last_view": "overview",
    "window_geometry": "1440x900",
    "compact_mode": False,
    "watchlist": ["SPY", "QQQ", "GLD", "XLK"],
}
WATCHLIST_MAX = 8
NATIVE_SETTINGS_KEYS = (
    "refresh_interval_seconds",
    "calendar_block_hours",
    "calendar_blocks_signals",
    "sentiment_blocks_signals",
    "macos_notifications",
)

ALLOWED_VIEWS = {
    "overview",
    "rotation",
    "forex",
    "assets",
    "global",
    "news",
    "history",
    "paper",
    "track",
    "report",
    "quality",
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
    if merged.get("last_view") not in ALLOWED_VIEWS:
        merged["last_view"] = DEFAULTS["last_view"]
    geom = str(merged.get("window_geometry") or DEFAULTS["window_geometry"])
    if "x" not in geom:
        geom = DEFAULTS["window_geometry"]
    merged["window_geometry"] = geom
    merged["compact_mode"] = bool(merged.get("compact_mode", False))
    merged["watchlist"] = normalize_watchlist(merged.get("watchlist"))
    return merged


def normalize_watchlist(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return list(DEFAULTS["watchlist"])
    cleaned: list[str] = []
    for item in raw:
        ticker = str(item or "").strip().upper()[:12]
        if ticker and ticker not in cleaned:
            cleaned.append(ticker)
        if len(cleaned) >= WATCHLIST_MAX:
            break
    return cleaned or list(DEFAULTS["watchlist"])


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


def native_settings_payload(settings: Dict[str, Any] | None = None) -> Dict[str, Any]:
    current = settings or load_user_settings()
    return {key: current[key] for key in NATIVE_SETTINGS_KEYS}


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
