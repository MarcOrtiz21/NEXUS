import random
import unittest

from gold_backtest_stats import purged_folds
from gold_calibration import (
    MIN_TRAIN_COMPACT,
    PENALTY_GRID,
    REGIME_FEATURE,
    _fit_compact,
    apply_shrinkage,
    drift_z,
    return_z,
    select_penalty,
    trend_probability,
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


def _return_rows(count=180, *, seed=11, drift=0.0004, beta=0.6):
    """Rendimientos sintéticos: deriva constante + efecto de un cambio de tipos reales."""
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        change = rng.gauss(0, 1)
        volatility = 0.01
        z = drift * 63 ** 0.5 / volatility - beta * change + rng.gauss(0, 1)
        month = 1 + index % 12
        year = 2005 + index // 12
        rows.append({
            "decision_at": f"{year}-{month:02d}-15",
            "evaluated_at": f"{year}-{month:02d}-28",
            "horizon_days": 63,
            "direction_up": int(z > 0),
            "log_return": z * volatility * 63 ** 0.5,
            "trend_drift": drift,
            "trend_volatility": volatility,
            "model_probability": 50.0,
            "group_signals": {},
            "compact_features": {
                "real_yield_change_3m": change, "breakeven_change_3m": rng.gauss(0, 1),
                "dollar_momentum_3m": None, "gold_momentum_12m": rng.gauss(0, 1), "vix_log": 3.0,
            },
        })
    return rows


class CompactCandidateTests(unittest.TestCase):
    def test_trend_probability_follows_drift_over_volatility(self):
        row = {"horizon_days": 63, "trend_drift": 0.0004, "trend_volatility": 0.01}
        self.assertAlmostEqual(drift_z(row), 0.0004 * 63 ** 0.5 / 0.01)
        self.assertGreater(trend_probability(row), 60)
        self.assertLess(trend_probability({**row, "trend_drift": -0.0004}), 40)
        self.assertIsNone(trend_probability({"horizon_days": 63}))

    def test_return_z_scales_by_horizon_volatility(self):
        row = {"horizon_days": 63, "trend_volatility": 0.01, "log_return": 0.0794}
        self.assertAlmostEqual(return_z(row), 0.0794 / (0.01 * 63 ** 0.5))

    def test_compact_models_learn_negative_real_rate_effect(self):
        rows = _return_rows()
        for kind in ("compact_logistic", "return_compact", "return_trend"):
            predict = _fit_compact(kind, rows, 2.0)
            base = rows[0]
            rising = {**base, "compact_features": {**base["compact_features"], "real_yield_change_3m": 2.0}}
            falling = {**base, "compact_features": {**base["compact_features"], "real_yield_change_3m": -2.0}}
            self.assertLess(predict(rising), predict(falling), kind)

    def test_missing_trend_inputs_give_no_return_prediction(self):
        predict = _fit_compact("return_trend", _return_rows(), 2.0)
        self.assertIsNone(predict({**_return_rows(1)[0], "trend_drift": None}))
        self.assertIsNone(_fit_compact("return_compact", _return_rows(10), 2.0))

    def test_penalty_selection_uses_purged_inner_split(self):
        self.assertIn(select_penalty("return_trend", _return_rows()), PENALTY_GRID)
        self.assertEqual(select_penalty("return_trend", _return_rows(30)), 4.0)

    def test_walk_forward_adds_all_compact_candidates(self):
        folds = list(purged_folds(_return_rows()))
        evaluated = walk_forward_candidates(folds)
        self.assertTrue(all(row["trend_probability"] is not None for row in evaluated))
        offset = 0
        for train, test in folds:
            fold_rows = evaluated[offset:offset + len(test)]
            offset += len(test)
            for key in ("compact_logistic_probability", "return_compact_probability", "return_trend_probability"):
                expected = len(train) >= MIN_TRAIN_COMPACT
                self.assertTrue(all((row[key] is not None) == expected for row in fold_rows), key)
        self.assertTrue(any(row["return_trend_probability"] is not None for row in evaluated))
        self.assertTrue(all(row["return_trend_penalty"] in PENALTY_GRID + (4.0,) for row in evaluated))


if __name__ == "__main__":
    unittest.main()
