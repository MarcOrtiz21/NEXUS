import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_trading import summarize_paper_trading, update_paper_portfolio


class PaperTradingSummaryTests(unittest.TestCase):
    def _summarize(self, portfolio, trades, limit=2):
        with tempfile.TemporaryDirectory() as tmp:
            portfolio_path = Path(tmp) / "portfolio.json"
            trades_path = Path(tmp) / "trades.jsonl"
            portfolio_path.write_text(json.dumps(portfolio), encoding="utf-8")
            trades_path.write_text(
                "".join(json.dumps(trade) + "\n" for trade in trades),
                encoding="utf-8",
            )
            with patch("paper_trading.PAPER_PORTFOLIO_JSON", portfolio_path), patch(
                "paper_trading.PAPER_TRADES_JSONL", trades_path
            ):
                return summarize_paper_trading(limit=limit)

    def test_trade_count_is_total_before_list_limit(self):
        portfolio = {
            "starting_value": 100000,
            "current_value": 102000,
            "benchmark_spy_entry_price": 100,
            "benchmark_start_value": 100000,
            "benchmark_current_value": 110000,
        }

        summary = self._summarize(portfolio, [{"id": index} for index in range(5)])

        self.assertEqual(summary["trade_count"], 5)
        self.assertEqual(summary["returned_trade_count"], 2)
        self.assertEqual(len(summary["trades"]), 2)
        self.assertTrue(summary["benchmark_valid"])
        self.assertEqual(summary["data_warnings"], [])

    def test_implausible_benchmark_is_reported_without_mutating_file(self):
        portfolio = {
            "starting_value": 100000,
            "current_value": 100000,
            "benchmark_spy_entry_price": 100,
            "benchmark_start_value": 100000,
            "benchmark_current_value": 738179.99,
        }
        original = json.loads(json.dumps(portfolio))

        summary = self._summarize(portfolio, [])

        self.assertFalse(summary["benchmark_valid"])
        self.assertIsNone(summary["benchmark_return_pct"])
        self.assertIsNone(summary["alpha_vs_spy_pct"])
        self.assertIn("inverosímil", summary["data_warnings"][0])
        self.assertEqual(summary["portfolio"], original)

    def test_missing_benchmark_data_is_invalid(self):
        summary = self._summarize(
            {"starting_value": 100000, "current_value": 100500},
            [],
        )

        self.assertFalse(summary["benchmark_valid"])
        self.assertIn("incompleto", summary["data_warnings"][0])

    def test_existing_holdings_are_marked_before_rebalance(self):
        portfolio = {
            "starting_value": 100000,
            "current_value": 100000,
            "holdings": {"SPY": 500, "CASH": 50000},
            "entry_prices": {"SPY": 100},
            "benchmark_spy_entry_price": 100,
            "benchmark_start_value": 100000,
            "benchmark_current_value": 100000,
        }

        class Decision:
            allocation = {"SPY": 50, "CASH": 50}
            action = "MANTENER"
            score = 60

        with tempfile.TemporaryDirectory() as tmp:
            portfolio_path = Path(tmp) / "portfolio.json"
            trades_path = Path(tmp) / "trades.jsonl"
            portfolio_path.write_text(json.dumps(portfolio), encoding="utf-8")
            with patch("paper_trading.PAPER_PORTFOLIO_JSON", portfolio_path), patch(
                "paper_trading.PAPER_TRADES_JSONL", trades_path
            ):
                result = update_paper_portfolio(Decision(), {"SPY": 110})

        self.assertEqual(result["portfolio"]["current_value"], 105000)
        self.assertEqual(result["trade"]["pnl_since_last_pct"], 5.0)


if __name__ == "__main__":
    unittest.main()
