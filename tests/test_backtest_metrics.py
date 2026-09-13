import unittest

from backtest import _metrics


class BacktestMetricTests(unittest.TestCase):
    def test_metrics_include_annualized_return_sharpe_and_drawdown(self):
        metrics = _metrics([1.0, 1.02, 1.01, 1.05], periods_per_year=52)

        self.assertAlmostEqual(metrics["total_return"], 0.05)
        self.assertGreater(metrics["annualized_return"], metrics["total_return"])
        self.assertGreater(metrics["volatility"], 0)
        self.assertIsInstance(metrics["sharpe"], float)
        self.assertLess(metrics["max_drawdown"], 0)

    def test_flat_series_has_zero_risk_metrics(self):
        metrics = _metrics([1.0, 1.0, 1.0], periods_per_year=52)

        self.assertEqual(metrics["volatility"], 0)
        self.assertEqual(metrics["sharpe"], 0)
        self.assertEqual(metrics["max_drawdown"], 0)


if __name__ == "__main__":
    unittest.main()
