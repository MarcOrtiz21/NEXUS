import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from paper_trading import summarize_paper_trading, update_paper_portfolio
from user_settings import DEFAULTS, save_user_settings, load_user_settings, get_setting, USER_SETTINGS_FILE


class UserSettingsTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.settings_path = Path(self._tmpdir.name) / "user_settings.json"
        patcher = patch("user_settings.USER_SETTINGS_FILE", self.settings_path)
        self.addCleanup(patcher.stop)
        patcher.start()
        patcher2 = patch("user_settings._settings_cache", None)
        self.addCleanup(patcher2.stop)
        patcher2.start()

    def test_save_and_load_settings(self):
        saved = save_user_settings({"refresh_interval_seconds": 120, "calendar_block_hours": 3})
        self.assertEqual(saved["refresh_interval_seconds"], 120)
        self.assertEqual(get_setting("calendar_block_hours"), 3)

    def test_invalid_values_fallback_to_defaults(self):
        save_user_settings({"calendar_block_hours": 99, "refresh_interval_seconds": 10})
        settings = load_user_settings(force=True)
        self.assertEqual(settings["calendar_block_hours"], DEFAULTS["calendar_block_hours"])
        self.assertGreaterEqual(settings["refresh_interval_seconds"], 60)


class PaperBenchmarkTests(unittest.TestCase):
    def test_benchmark_tracks_spy_buy_and_hold(self):
        class Decision:
            action = "COMPRAR"
            score = 80
            allocation = {"SPY": 60, "QQQ": 0, "TLT": 10, "GLD": 10, "UUP": 0, "CASH": 20}

        with tempfile.TemporaryDirectory() as tmp:
            portfolio_path = Path(tmp) / "paper.json"
            trades_path = Path(tmp) / "trades.jsonl"
            with patch("paper_trading.PAPER_PORTFOLIO_JSON", portfolio_path):
                with patch("paper_trading.PAPER_TRADES_JSONL", trades_path):
                    update_paper_portfolio(Decision(), {"SPY": 100.0, "QQQ": 200.0, "TLT": 90.0, "GLD": 180.0, "UUP": 28.0})
                    update_paper_portfolio(Decision(), {"SPY": 110.0, "QQQ": 210.0, "TLT": 91.0, "GLD": 181.0, "UUP": 29.0})
                    summary = summarize_paper_trading()

        self.assertEqual(summary["benchmark_return_pct"], 10.0)
        self.assertIn("alpha_vs_spy_pct", summary)


if __name__ == "__main__":
    unittest.main()
