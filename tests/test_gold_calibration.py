import random
import unittest

from gold_backtest_stats import purged_folds
from gold_calibration import (
    REGIME_FEATURE,
    apply_shrinkage,
    calibrate_live_horizon,
    fit_ridge_logistic,
    fit_shrinkage,
    predict_logistic,
    walk_forward_candidates,
)


def _rows(count=120, *, informative: bool, seed=7):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        signal = rng.uniform(-1, 1)
        up = int(rng.random() < (0.5 + 0.4 * signal if informative else 0.6))
        month = 1 + index % 12
        year = 2016 + index // 12
        rows.append({
            "decision_at": f"{year}-{month:02d}-15",
            "evaluated_at": f"{year}-{month:02d}-28",
            "direction_up": up,
            "model_probability": 50 + 35 * signal,
            "group_signals": {"real_rates": signal},
        })
    return rows


class GoldCalibrationTests(unittest.TestCase):
    def test_noise_signal_shrinks_to_base_rate(self):
        params = fit_shrinkage(_rows(informative=False))
        self.assertLessEqual(params["k"], 0.2)
        self.assertAlmostEqual(apply_shrinkage(80, params["base_pct"], 0.0), params["base_pct"])

    def test_informative_signal_keeps_deviation(self):
        self.assertGreaterEqual(fit_shrinkage(_rows(informative=True))["k"], 0.6)

    def test_logistic_learns_sign_and_regime_feature(self):
        rows = _rows(informative=True)
        model = fit_ridge_logistic(rows, regime=True)
        self.assertGreater(model["coefficients"]["real_rates"], 0)
        self.assertIn(REGIME_FEATURE, model["coefficients"])
        high = predict_logistic(model, {**rows[0], "group_signals": {"real_rates": 1.0}}, regime=True)
        low = predict_logistic(model, {**rows[0], "group_signals": {"real_rates": -1.0}}, regime=True)
        self.assertGreater(high, low)

    def test_insufficient_training_is_not_fitted(self):
        self.assertEqual(fit_shrinkage(_rows(10, informative=True))["status"], "INSUFFICIENT_DATA")
        self.assertIsNone(predict_logistic(fit_ridge_logistic(_rows(10, informative=True), regime=False), {}, regime=False))

    def test_walk_forward_uses_only_matured_training(self):
        rows = _rows(informative=True)
        folds = list(purged_folds(rows))
        evaluated = walk_forward_candidates(folds)
        self.assertEqual(len(evaluated), sum(len(test) for _, test in folds))
        for train, test in folds:
            self.assertTrue(all(row["evaluated_at"] < test[0]["decision_at"] for row in train))
        self.assertTrue(all(row["learned_regime_probability"] is not None for row in evaluated))

    def test_live_horizon_keeps_heuristic_probability(self):
        horizon = {"probability_up": 40.0, "label": "NEUTRAL"}
        calibrated = calibrate_live_horizon(
            horizon, {"shrinkage": {"status": "FITTED", "base_pct": 60.0, "k": 0.0, "sample_size": 100}}, eligible=True
        )
        self.assertEqual(calibrated["probability_up"], 40.0)
        self.assertEqual(calibrated["probability_calibrated"], 60.0)
        self.assertIn("frecuencia histórica", calibrated["calibration"]["note"])
        missing = calibrate_live_horizon(horizon, None, eligible=False)
        self.assertEqual(missing["calibration"]["status"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
