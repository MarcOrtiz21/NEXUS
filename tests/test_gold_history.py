import sqlite3
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from gold_history import gold_change_summary, gold_history_summary, record_gold_snapshot
from gold_validation import (
    balanced_accuracy,
    brier_score,
    calibration_bins,
    settle_predictions_from_prices,
    validation_summary,
    walk_forward_splits,
)


def outlook(short_days=21, medium_days=63):
    return {
        "version": "gold-outlook-test",
        "status": "PRELIMINARY",
        "short_term": {
            "horizon_days": short_days,
            "probability_up": 60,
            "score": 20,
            "label": "ALCISTA",
            "confidence": "MEDIA",
            "coverage_pct": 80,
        },
        "medium_term": {
            "horizon_days": medium_days,
            "probability_up": 40,
            "score": -20,
            "label": "BAJISTA",
            "confidence": "BAJA",
            "coverage_pct": 70,
        },
        "groups": [{
            "id": "inflation",
            "available": True,
            "coverage_pct": 100,
            "short_contribution": 4,
            "medium_contribution": -2,
        }],
    }


class GoldHistoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "gold.sqlite3"

    def tearDown(self):
        self.temp.cleanup()

    def test_records_revisions_without_duplicating_unchanged_values(self):
        data = {
            "CPI_YoY_Pct": 3.0,
            "CPI_AsOf": "2026-08-01",
            "VIX": 18.0,
            "Assets": {"GLD": {"price": 200.0}},
            "DataQuality": {
                "CPI_YoY_Pct": {"source": "FRED:CPIAUCSL", "status": "OK"},
                "VIX": {"source": "yfinance:^VIX", "status": "OK"},
            },
        }
        first = record_gold_snapshot(
            data, outlook(), captured_at="2026-09-15T12:00:00+00:00", db_path=self.db
        )
        duplicate = record_gold_snapshot(
            data, outlook(), captured_at="2026-09-15T12:05:00+00:00", db_path=self.db
        )
        data["CPI_YoY_Pct"] = 3.1
        revised = record_gold_snapshot(
            data, outlook(), captured_at="2026-09-16T12:00:00+00:00", db_path=self.db
        )

        self.assertEqual(first["observations_inserted"], 2)
        self.assertEqual(duplicate["observations_inserted"], 0)
        self.assertEqual(duplicate["prediction_inserted"], 0)
        self.assertEqual(revised["observations_inserted"], 2)  # CPI revisado + nuevo VIX diario
        summary = gold_history_summary(self.db)
        self.assertEqual(summary["predictions"], 2)
        self.assertEqual(summary["observations"], 4)
        self.assertEqual(summary["point_in_time_observations"], 2)

        with sqlite3.connect(self.db) as connection:
            revisions = connection.execute(
                "SELECT revision FROM gold_observations WHERE metric='CPI_YoY_Pct' ORDER BY revision"
            ).fetchall()
        self.assertEqual(revisions, [(0,), (1,)])

    def test_rejects_observation_period_after_capture(self):
        result = record_gold_snapshot(
            {
                "CPI_YoY_Pct": 3.0,
                "CPI_AsOf": "2026-10-01",
                "Assets": {"GLD": {"price": 200.0}},
            },
            outlook(),
            captured_at="2026-09-15T12:00:00+00:00",
            db_path=self.db,
        )
        self.assertEqual(result["future_observations_rejected"], 1)
        self.assertEqual(gold_history_summary(self.db)["observations"], 0)

    def test_history_exposes_recent_predictions_and_change_summary(self):
        first = outlook()
        record_gold_snapshot(
            {"Assets": {"GLD": {"price": 100.0}}},
            first,
            captured_at="2026-09-15T12:00:00+00:00",
            db_path=self.db,
        )
        current = outlook()
        current["short_term"]["probability_up"] = 66
        current["groups"][0]["short_contribution"] = 7
        change = gold_change_summary(
            current,
            captured_at="2026-09-16T12:00:00+00:00",
            db_path=self.db,
        )
        self.assertEqual(change["short"]["delta_probability"], 6.0)
        self.assertEqual(change["drivers"][0]["short_delta"], 3.0)
        recent = gold_history_summary(self.db)["recent_predictions"]
        self.assertEqual(len(recent), 1)
        self.assertEqual(recent[0]["short_probability"], 60.0)

    def test_settlement_uses_only_sessions_after_prediction(self):
        record_gold_snapshot(
            {"Assets": {"GLD": {"price": 100.0}}},
            outlook(short_days=2, medium_days=3),
            captured_at="2026-01-10T18:00:00+00:00",
            db_path=self.db,
        )
        prices = [
            ("2026-01-10", 500.0),  # Debe ignorarse: mismo día de la captura.
            ("2026-01-11", 101.0),
            ("2026-01-12", 102.0),
            ("2026-01-13", 99.0),
        ]
        self.assertEqual(settle_predictions_from_prices(prices, db_path=self.db), 2)
        with sqlite3.connect(self.db) as connection:
            rows = connection.execute(
                "SELECT horizon_days, outcome_price FROM gold_prediction_outcomes ORDER BY horizon_days"
            ).fetchall()
        self.assertEqual(rows, [(2, 102.0), (3, 99.0)])


class GoldValidationTests(unittest.TestCase):
    def test_metrics_and_calibration(self):
        probabilities = [0.8, 0.7, 0.2, 0.3]
        outcomes = [1, 1, 0, 0]
        self.assertAlmostEqual(brier_score(probabilities, outcomes), 0.065)
        self.assertEqual(balanced_accuracy(probabilities, outcomes), 1.0)
        self.assertEqual(sum(row["count"] for row in calibration_bins(probabilities, outcomes)), 4)

    def test_walk_forward_never_overlaps_future_with_training(self):
        splits = walk_forward_splits(40, min_train=24, test_size=6)
        self.assertEqual(len(splits), 3)
        for train, test in splits:
            self.assertLess(max(train), min(test))

    def test_empty_validation_is_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            summary = validation_summary(horizon_days=21, db_path=Path(temp) / "missing.sqlite3")
        self.assertEqual(summary["status"], "INSUFFICIENT_DATA")
        self.assertEqual(summary["sample_size"], 0)


if __name__ == "__main__":
    unittest.main()
