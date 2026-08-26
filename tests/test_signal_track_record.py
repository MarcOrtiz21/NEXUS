import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from signal_track_record import (
    evaluate_track_record,
    format_track_record_report,
    history_buy_scale,
    track_record_chart_payload,
)


def _row(captured_at: str, action: str, spy_price: float, macro_action: str | None = None):
    return {
        "captured_at": captured_at,
        "action": action,
        "macro_action": macro_action or action,
        "operational_action": action,
        "score": 70,
        "prices": {"SPY": spy_price},
    }


class SignalTrackRecordTests(unittest.TestCase):
    def test_evaluate_track_record_computes_forward_returns(self):
        rows = [
            _row("2026-01-01T12:00:00+00:00", "COMPRAR", 100.0),
            _row("2026-01-06T12:00:00+00:00", "ESPERAR", 105.0),
            _row("2026-01-11T12:00:00+00:00", "ESPERAR", 103.0),
        ]
        with patch("signal_track_record.load_history_jsonl", return_value=rows):
            summary = evaluate_track_record(forward_days=5, limit=10)

        self.assertEqual(summary["sample_size"], 2)
        self.assertEqual(summary["macro_buy_count"], 1)
        self.assertEqual(summary["macro_buy_avg_return_pct"], 5.0)

    def test_macro_vs_operational_layers(self):
        rows = [
            {
                "captured_at": "2026-01-01T12:00:00+00:00",
                "action": "ESPERAR",
                "macro_action": "COMPRAR",
                "operational_action": "ESPERAR",
                "score": 78,
                "prices": {"SPY": 100.0},
            },
            {
                "captured_at": "2026-01-06T12:00:00+00:00",
                "action": "ESPERAR",
                "macro_action": "ESPERAR",
                "operational_action": "ESPERAR",
                "score": 40,
                "prices": {"SPY": 98.0},
            },
        ]
        with patch("signal_track_record.load_history_jsonl", return_value=rows):
            summary = evaluate_track_record(forward_days=5, limit=10)

        self.assertEqual(summary["macro_buy_count"], 1)
        self.assertEqual(summary["defensive_count"], 1)

    def test_format_report_handles_empty_history(self):
        with patch("signal_track_record.load_history_jsonl", return_value=[]):
            report = format_track_record_report()
        self.assertIn("Historial insuficiente", report)

    def test_chart_payload_includes_series_and_hit_bars(self):
        rows = [
            _row("2026-01-01T12:00:00+00:00", "COMPRAR", 100.0),
            _row("2026-01-06T12:00:00+00:00", "ESPERAR", 105.0),
            _row("2026-01-11T12:00:00+00:00", "ESPERAR", 103.0),
        ]
        with patch("signal_track_record.load_history_jsonl", return_value=rows):
            payload = track_record_chart_payload(forward_days=5, limit=10, chart_limit=10)

        self.assertEqual(payload["sample_size"], 2)
        self.assertEqual(len(payload["chart_samples"]), 2)
        self.assertEqual(len(payload["hit_bars"]), 2)
        self.assertIn("Macro COMPRAR", payload["hit_bars"][0]["label"])

    def test_rejects_forward_observation_too_far_from_target(self):
        rows = [
            _row("2026-01-01T12:00:00+00:00", "COMPRAR", 100.0),
            _row("2026-02-01T12:00:00+00:00", "ESPERAR", 120.0),
        ]
        with patch("signal_track_record.load_history_jsonl", return_value=rows):
            summary = evaluate_track_record(forward_days=5, limit=10)

        self.assertEqual(summary["sample_size"], 0)

    def test_evaluates_twenty_day_horizon_and_vix_buckets(self):
        rows = [
            {**_row("2026-01-01T12:00:00+00:00", "COMPRAR", 100.0), "vix": 14.0},
            {**_row("2026-01-06T12:00:00+00:00", "COMPRAR", 102.0), "vix": 14.0},
            {**_row("2026-01-21T12:00:00+00:00", "ESPERAR", 108.0), "vix": 18.0},
        ]
        with patch("signal_track_record.load_history_jsonl", return_value=rows):
            summary = evaluate_track_record(forward_days=5, limit=10)

        self.assertEqual(summary["macro_buy_count"], 1)
        self.assertEqual(summary["macro_buy_count_20d"], 1)
        self.assertEqual(summary["macro_buy_hit_rate_20d_pct"], 100.0)
        self.assertEqual(summary["vix_buckets"]["calma"]["count"], 1)

    def test_history_buy_scale_needs_enough_samples(self):
        scale, reason = history_buy_scale({
            "macro_buy_count": 3,
            "macro_buy_hit_rate_pct": 20.0,
        })
        self.assertEqual(scale, 1.0)
        self.assertIsNone(reason)

        weak, weak_reason = history_buy_scale({
            "macro_buy_count": 10,
            "macro_buy_hit_rate_pct": 30.0,
        })
        self.assertEqual(weak, 0.7)
        self.assertIn("no confirma", weak_reason)


if __name__ == "__main__":
    unittest.main()
