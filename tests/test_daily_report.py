import unittest
from unittest.mock import patch

from daily_report import build_daily_report


class DailyReportTests(unittest.TestCase):
    def test_build_daily_report_contains_sections(self):
        snapshot = {
            "captured_at_utc": "2026-07-13T19:00:00+00:00",
            "status": "HEALTHY",
            "alerts": ["alerta prueba"],
            "data": {
                "VIX": 16.0,
                "US10Y": 4.5,
                "Yield_Curve_Spread": 0.4,
                "CPI_YoY_Pct": 3.0,
                "M2_Change_Pct": 1.5,
                "GlobalMarkets": {"Europa": {"momentum_1m": 1.0}},
            },
            "decision": {
                "macro_action": "COMPRAR",
                "operational_action": "COMPRAR",
                "action": "COMPRAR",
                "score": 78,
                "confidence": "ALTA",
            },
            "rotation": {"state": "ROTACION", "leaders_avg_1m": 2.0, "receivers_avg_1m": 3.0},
        }
        with patch("daily_report.summarize_paper_trading", return_value={"total_return_pct": 1.0, "benchmark_return_pct": 0.5, "alpha_vs_spy_pct": 0.5}):
            with patch("daily_report.evaluate_track_record", return_value={"sample_size": 3, "macro_buy_hit_rate_pct": 66.0}):
                report = build_daily_report(snapshot)
        self.assertIn("INFORME DIARIO NEXUS", report["text"])
        self.assertIn("PAPER TRADING", report["text"])
        self.assertIn("<html", report["html"])


if __name__ == "__main__":
    unittest.main()
