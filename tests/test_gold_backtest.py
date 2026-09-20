import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from gold_backtest import _decision_dates, run_gold_backtest


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
        with tempfile.TemporaryDirectory() as folder:
            report = run_gold_backtest(
                start=date(2016, 1, 1), end=date(2025, 12, 31),
                report_path=Path(folder) / "report.json", market_prices=prices, vintage_series=series,
                cftc_rows=[],
            )
        self.assertTrue(report["point_in_time"])
        self.assertGreaterEqual(report["horizons"]["63"]["model"]["sample_size"], 30)
        self.assertIn("inflation", report["horizons"]["21"]["ablation"])
        self.assertIn(
            report["horizons"]["21"]["ablation"]["inflation"]["interpretation"],
            {"APORTA", "NEUTRAL", "REVISAR"},
        )
        for sample in report["samples"]:
            self.assertLessEqual(sample["latest_release_at"], sample["decision_at"])


if __name__ == "__main__":
    unittest.main()
