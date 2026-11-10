import json
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from gold_outlook import _horizon, MODEL_VERSION
from gold_backtest import _candidate_report, _calibration_eligible, load_gold_backtest_report
from gold_history import record_gold_snapshot
from gold_validation import validation_summary


def prediction(identity="a"):
    return {"version": MODEL_VERSION, "model_fingerprint": identity, "groups": [],
            "short_term": {"probability_up": 60}, "medium_term": {"probability_up": 40}}


class GoldReliabilityTests(unittest.TestCase):
    def test_thirty_overlapping_results_do_not_publish_validation(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"gold.sqlite3"
            for i in range(31):
                day = date(2026, 1, 1) + timedelta(days=i)
                record_gold_snapshot({"Assets": {"GLD": {"price": 100}}}, prediction(),
                                     captured_at=f"{day}T12:00:00+00:00", db_path=path)
            with sqlite3.connect(path) as c:
                c.execute("INSERT INTO gold_prediction_outcomes SELECT id,21,'2026-03-01',101,1,1 FROM gold_predictions")
            result = validation_summary(horizon_days=21, db_path=path)
            self.assertEqual(result["sample_size"], 31)
            self.assertEqual(result["non_overlapping_count"], 1)
            self.assertFalse(result["metrics_publishable"])

    def test_stale_data_does_not_count_as_fresh_or_predictively_reliable(self):
        group = {"id": "a", "label": "a", "note": "", "short_signal": 1, "short_weight": 1,
                 "short_contribution": 100, "details": [{"available": True, "quality": "STALE"}]}
        result = _horizon([group], "short")
        self.assertEqual(result["confidence"], "BAJA")
        self.assertEqual(result["fresh_coverage_pct"], 0)
        self.assertEqual(result["signal_strength"], "FUERTE")
        self.assertEqual(result["predictive_reliability"], "NO_DEMOSTRADA")

    def test_small_average_gain_does_not_activate_calibration(self):
        self.assertFalse(_calibration_eligible({"candidates": {"calibrated": {
            "status": "EVALUATED", "brier_score": .24, "passes_baselines": False}},
            "model": {"brier_score": .26}, "baseline_constant": {"brier_score": .25}}))

    def test_incompatible_report_cannot_enable_live_features(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"report.json"
            path.write_text(json.dumps({"model_version": "old", "live_calibration": {"21": {"eligible": True}},
                                      "feature_gates": {"positioning": "ENABLED"}}))
            report = load_gold_backtest_report(path)
            self.assertFalse(report["compatible_with_live"])
            self.assertEqual(report["live_calibration"], {})
            self.assertEqual(report["feature_gates"]["positioning"], "CONTEXT_ONLY")

    def test_candidate_delta_uses_identical_cuts(self):
        rows = [{"decision_at": f"{2000+i}-01-01", "evaluated_at": f"{2000+i}-02-01",
                 "return_pct": 1, "direction_up": i % 2, "model_probability": 50,
                 "candidate": 50, "constant_probability": 50, "historical_probability": 50,
                 "momentum_probability": 50, "macro_probability": 50} for i in range(30)]
        report = _candidate_report(rows, "candidate", {"brier_score": .4})
        self.assertEqual(report["delta_brier_vs_model"], 0)
        self.assertFalse(report["passes_baselines"])

    def test_event_and_configuration_captures_are_immutable_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"gold.sqlite3"
            def capture(hour, identity="a", event=None):
                return record_gold_snapshot({"Assets": {"GLD": {"price": 100}}}, prediction(identity),
                    captured_at=f"2026-10-06T{hour}:00:00+00:00", capture_context={"trigger_event": event}, db_path=path)
            self.assertEqual(capture("10")["prediction_inserted"], 1)
            self.assertEqual(capture("11")["prediction_inserted"], 0)
            self.assertEqual(capture("12", event="CPI")["prediction_inserted"], 1)
            self.assertEqual(capture("13", event="CPI")["prediction_inserted"], 0)
            self.assertEqual(capture("14", identity="b")["prediction_inserted"], 1)
            with sqlite3.connect(path) as c:
                self.assertEqual(c.execute("SELECT count(*) FROM gold_predictions").fetchone()[0], 3)
                rows = c.execute("SELECT id FROM gold_predictions").fetchall()
                for row in rows:
                    c.execute("INSERT INTO gold_prediction_outcomes VALUES (?,21,'2026-11-06',101,1,1)", row)
            summary = validation_summary(horizon_days=21, db_path=path, model_version=MODEL_VERSION, model_fingerprint="a")
            self.assertEqual(summary["sample_size"], 2)
            self.assertEqual(summary["non_overlapping_count"], 1)
            self.assertFalse(summary["metrics_publishable"])
