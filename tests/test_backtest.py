import unittest

from backtest import _max_drawdown, _metrics


class BacktestMathTests(unittest.TestCase):
    def test_max_drawdown_detects_peak_to_trough_loss(self):
        self.assertAlmostEqual(_max_drawdown([1.0, 1.2, 0.9, 1.1]), -0.25)

    def test_metrics_returns_total_return(self):
        metrics = _metrics([1.0, 1.1, 1.21], periods_per_year=52)

        self.assertAlmostEqual(metrics["total_return"], 0.21)
        self.assertIn("volatility", metrics)
        self.assertIn("max_drawdown", metrics)


if __name__ == "__main__":
    unittest.main()
