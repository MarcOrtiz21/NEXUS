import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from signal_track_record import evaluate_track_record, format_track_record_report


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


if __name__ == "__main__":
    unittest.main()
