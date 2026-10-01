import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from gld_holdings import release_at_for_session
from gold_backtest import _decision_dates, _regime_diagnostics, run_gold_backtest


def _monthly_rows(start="2012-01-01", periods=180, base=100.0):
    dates = pd.date_range(start, periods=periods, freq="MS")
    return [
        {"period": day.date().isoformat(), "release_at": (day + pd.Timedelta(days=40)).date().isoformat(), "value": base + index}
        for index, day in enumerate(dates)
    ]


def _daily_rows(start="2012-01-01", periods=4000, base=2.0):
    dates = pd.bdate_range(start, periods=periods)
    return [
        {"period": day.date().isoformat(), "release_at": day.date().isoformat(), "value": base + index * 0.0001}
        for index, day in enumerate(dates)
    ]


class GoldBacktestTests(unittest.TestCase):
    def test_regime_diagnostics_withhold_small_sample_conclusions(self):
        rows = [{"macro_regime": "EASING", "model_probability": 60.0, "direction_up": 1}] * 3
        diagnostics = _regime_diagnostics(rows)
        self.assertEqual(diagnostics["EASING"]["status"], "INSUFFICIENT_DATA")
        self.assertIsNone(diagnostics["EASING"]["model_brier"])

    def test_decision_is_first_session_on_or_after_fifteenth(self):
        index = pd.bdate_range("2024-01-01", "2024-03-31")
        dates = _decision_dates(index, date(2024, 1, 1), date(2024, 3, 31))
        self.assertTrue(all(day.day >= 15 for day in dates))
        self.assertEqual(len(dates), 3)

    def test_backtest_never_uses_future_release(self):
        index = pd.bdate_range("2014-01-01", "2025-12-31")
        prices = pd.DataFrame({
            "GLD": [100 + i * 0.02 for i in range(len(index))],
            "UUP": [25 + i * 0.001 for i in range(len(index))],
            "^VIX": [18.0 for _ in index],
        }, index=index)
        series = {name: _monthly_rows() for name in (
            "cpi", "core_cpi", "pce", "core_pce", "energy_cpi", "unemployment", "payrolls", "industrial", "m2"
        )}
        series.update({name: _daily_rows() for name in ("real_yield", "breakeven", "wti")})
        holdings = [
            {
                "date": day.date().isoformat(),
                "release_at": release_at_for_session(day.date()).isoformat(timespec="seconds"),
                "tonnes": 500 + (index % 90) * 0.5,
            }
            for index, day in enumerate(index)
        ]
        with tempfile.TemporaryDirectory() as folder:
            report = run_gold_backtest(
                start=date(2016, 1, 1), end=date(2025, 12, 31),
                report_path=Path(folder) / "report.json", market_prices=prices, vintage_series=series,
                cftc_rows=[], gld_holdings_rows=holdings,
            )
        self.assertTrue(report["point_in_time"])
        self.assertGreaterEqual(report["horizons"]["63"]["model"]["sample_size"], 30)
        self.assertIn("inflation", report["horizons"]["21"]["ablation"])
        self.assertEqual(report["report_schema_version"], 2)
        self.assertEqual(report["horizons"]["21"]["baseline_constant"]["brier_score"], 0.25)
        self.assertLess(report["horizons"]["63"]["overlap"]["non_overlapping_count"], report["horizons"]["63"]["model"]["sample_size"])
        for horizon in report["horizons"].values():
            for fold in horizon["walk_forward_folds"]:
                self.assertLess(fold["train_last_outcome"], fold["test_from"])
        self.assertTrue(report["horizons"]["21"]["macro_regimes"])
        self.assertIn(
            report["horizons"]["21"]["ablation"]["inflation"]["interpretation"],
            {"APORTA", "NEUTRAL", "REVISAR"},
        )
        self.assertIn(report["feature_gates"]["etf_holdings"], {"ENABLED", "CONTEXT_ONLY"})
        self.assertIn("etf_holdings", report["horizons"]["21"]["ablation"])
        for sample in report["samples"]:
            self.assertLessEqual(sample["latest_release_at"], sample["decision_at"])
            self.assertLessEqual(sample["latest_gld_holdings_release_at"][:10], sample["decision_at"])


if __name__ == "__main__":
    unittest.main()
