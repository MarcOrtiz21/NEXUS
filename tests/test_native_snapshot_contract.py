"""Contrato JSON compartido con Swift. Los insumos son inventados y no hay E/S del motor."""

import json
import sys
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from history_view import summarize_history
from native_api import build_native_snapshot


FIXTURE = Path(__file__).parent / "fixtures" / "native_snapshot.json"
CAPTURED_AT = "2026-01-08T14:00:00+00:00"


class FixtureClock(datetime):
    @classmethod
    def now(cls, tz=None):
        return datetime.fromisoformat(CAPTURED_AT).astimezone(tz or timezone.utc)


def fixture_json() -> str:
    history_rows = [
        {"captured_at": "2026-01-07T14:00:00+00:00", "score": 61,
         "action": "COMPRAR", "prices": {"SPY": 120.0}},
        {"captured_at": CAPTURED_AT, "score": 58,
         "action": "ESPERAR", "prices": {"SPY": 123.45}},
    ]
    event = {"title": "CPI · evento de prueba", "when_utc": "2026-01-08T16:00:00+00:00",
             "hours_until": 2.0, "blocks_signals": True, "source": "fixture"}
    raw = {
        "captured_at_utc": CAPTURED_AT,
        "status_value": "BLOCKED",
        "alerts": ["Alerta sintética"],
        "calendar": {
            "should_block_signals": True, "block_hours": 6, "time_quality": "oficial",
            "next_event": event, "events_detail": [event], "source": "fixture",
        },
        "decision_dict": {
            "action": "ESPERAR", "operational_action": "ESPERAR", "macro_action": "COMPRAR",
            "operational_pause_reason": "Pausa de prueba", "score": 58,
            "allocation": {"CASH": 100}, "macro_allocation": {"SPY": 25, "CASH": 75},
        },
        "data": {
            "VIX": 19.5,
            "Assets": {"SPY": {"price": 123.45, "momentum_1m": 1.25}, "GLD": {"price": 45.6}},
            "Forex": {"EURUSD": {"price": 1.125}},
            "Freshness": {
                "market": {"status": "OK", "age_seconds": 15},
                "macro": {"status": "OK", "age_seconds": 120, "as_of": "2026-01-07"},
                "companies": {"status": "PARTIAL", "age_seconds": 240, "available": 1, "total": 2},
            },
            "PriceSparklines": {"SPY": [{"date": "2026-01-08", "value": 123.45}]},
            "GoldOfficialDemand": {
                "status": "PARTIAL",
                "reserves": [{"id": "fixture-reserve", "tonnes": 12.5, "as_of": "2026-01-07"}],
                "score_enabled": False,
            },
        },
        "rotation_dict": {
            "themes": [{"ticker": "XLK", "theme": "Sector de prueba", "score": 62,
                        "companies": [{"ticker": "TEST", "name": "Empresa de prueba", "price": 23.4}]}],
        },
        "news_items": [
            {"title": "Oro · titular sintético", "source": "Fuente de prueba",
             "url": "https://example.invalid/oro", "linked_assets": ["GLD"]},
            {"title": "Divisas · titular sintético", "source": "Fuente de prueba",
             "url": "https://example.invalid/divisas", "linked_assets": ["EURUSD"]},
        ],
    }
    settings = {
        "refresh_interval_seconds": 600, "calendar_block_hours": 6, "calendar_blocks_signals": True,
        "sentiment_blocks_signals": True, "macos_notifications": False, "watchlist": ["SPY", "GLD"],
    }
    # Se ejecuta el constructor real; se sustituyen solo sus entradas externas.
    dependencies = {
        "build_snapshot": raw,
        "load_history_jsonl": history_rows,
        "load_history_period": history_rows,
        "evaluate_track_record": {},
        "summarize_paper_trading": {"trade_count": 0},
        "load_gold_backtest_report": {"status": "NOT_RUN", "horizons": {}},
        "gold_history_summary": {"observations": 0, "predictions": 0, "settled_outcomes": 0},
        "gold_change_summary": None,
        "validation_summary": {"status": "INSUFFICIENT_DATA", "sample_size": 0},
        "update_experiment": {"status": "NOT_REGISTERED", "score_enabled": False},
    }

    def fixture_history(*args, rows=None, **kwargs):
        return summarize_history(*args, rows=history_rows if rows is None else rows, **kwargs)

    with ExitStack() as stack:
        for name, value in dependencies.items():
            stack.enter_context(patch(f"native_api.{name}", return_value=value))
        stack.enter_context(patch("native_api.summarize_history", side_effect=fixture_history))
        stack.enter_context(patch("native_api.get_setting", side_effect=settings.__getitem__))
        stack.enter_context(patch("risk_filters.sentiment._finbert_enabled", return_value=False))
        stack.enter_context(patch("native_api.datetime", FixtureClock))
        stack.enter_context(patch("decision_intelligence.datetime", FixtureClock))
        snapshot = build_native_snapshot(export=False)
    # La huella del código de oro no es parte de este contrato de tipos/valores.
    if snapshot.get("gold", {}).get("outlook", {}).get("model_fingerprint"):
        snapshot["gold"]["outlook"]["model_fingerprint"] = "synthetic-fixture"
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n"


class NativeSnapshotFixtureTests(unittest.TestCase):
    def test_python_output_matches_swift_fixture(self):
        # Comparar el JSON canónico también distingue true de 1 (iguales en Python).
        self.assertMultiLineEqual(
            FIXTURE.read_text(encoding="utf-8"),
            fixture_json(),
            "Cambió el contrato de /api/native: revisa el diff, el modelo Swift y el fixture.",
        )


if __name__ == "__main__":
    if sys.argv[1:] == ["--emit-fixture"]:
        sys.stdout.write(fixture_json())
    else:
        unittest.main()
