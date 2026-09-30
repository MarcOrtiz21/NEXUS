import unittest

from gold_backtest_stats import assign_historical_baseline, overlap_diagnostics, paired_brier_interval, purged_folds


class GoldBacktestStatisticsTests(unittest.TestCase):
    def test_frequency_never_trains_on_unsettled_results(self):
        rows = [
            {"decision_at": "2024-01-01", "evaluated_at": "2024-04-01", "direction_up": 1},
            {"decision_at": "2024-02-01", "evaluated_at": "2024-03-01", "direction_up": 0},
            {"decision_at": "2024-03-15", "evaluated_at": "2024-06-01", "direction_up": 1},
        ]
        assign_historical_baseline(rows, minimum=1)
        self.assertIsNone(rows[1]["historical_probability"])
        self.assertEqual(rows[2]["historical_probability"], 0.0)
        self.assertEqual(rows[2]["historical_train_size"], 1)
        self.assertEqual(overlap_diagnostics(rows)["non_overlapping_count"], 1)

    def test_fold_purges_training_outcomes_overlapping_test(self):
        rows = [{"decision_at": f"2024-01-{day:02d}", "evaluated_at": f"2024-01-{day + 3:02d}",
                 "direction_up": day % 2} for day in range(1, 20)]
        folds = list(purged_folds(rows, minimum=4, test_size=3))
        self.assertTrue(folds)
        for train, test in folds:
            self.assertTrue(all(row["evaluated_at"] < test[0]["decision_at"] for row in train))

    def test_identical_probabilities_show_no_statistical_gain(self):
        rows = [{"decision_at": f"{2000 + i}-01-01", "evaluated_at": f"{2000 + i}-02-01",
                 "direction_up": i % 2, "model_probability": 50.0, "constant_probability": 50.0} for i in range(40)]
        interval = paired_brier_interval(rows, "constant_probability", draws=100)
        self.assertEqual(interval["lower"], 0)
        self.assertEqual(interval["upper"], 0)
        self.assertEqual(interval["delta_brier"], 0)
