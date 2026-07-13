import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from decision_engine import DecisionEngine
from logic_engine import MarketStatus
from risk_filters.fred_calendar import fetch_fred_release_events


class FredCalendarTests(unittest.TestCase):
    def test_fetch_fred_release_events_parses_payload(self):
        now = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
        payload = {
            "release_dates": [
                {"date": "2026-07-14"},
                {"date": "2026-08-12"},
            ]
        }
        with patch("risk_filters.fred_calendar.FRED_API_KEY", "test-key"):
            with patch("risk_filters.fred_calendar.requests.get") as mock_get:
                mock_get.return_value.status_code = 200
                mock_get.return_value.json.return_value = payload
                mock_get.return_value.raise_for_status = lambda: None
                events = fetch_fred_release_events(lookahead_hours=48, now=now)
        self.assertTrue(events)
        self.assertTrue(all(event["source"] == "fred_release" for event in events))
        self.assertTrue(all(event["blocks_signals"] for event in events))


class GlobalScoreTests(unittest.TestCase):
    def _asset(self, price=100.0, ma20=95.0, ma50=90.0, ma200=85.0, mom1=3.0, mom3=8.0):
        return {
            "price": price,
            "ma20": ma20,
            "ma50": ma50,
            "ma200": ma200,
            "momentum_1m": mom1,
            "momentum_3m": mom3,
            "volatility_20d": 14.0,
        }

    def test_weak_china_and_europe_reduce_score(self):
        data = {
            "VIX": 14.0,
            "US10Y": 3.8,
            "Correlation_Proxy": 0.12,
            "PE_Forward": 17.0,
            "PE_Trailing": 24.0,
            "M2_Change_Pct": 1.8,
            "CPI_YoY_Pct": 2.6,
            "Assets": {
                "SPY": self._asset(),
                "QQQ": self._asset(price=120.0, ma20=112.0, ma50=108.0, ma200=100.0),
                "TLT": self._asset(),
                "GLD": self._asset(),
                "UUP": self._asset(),
            },
            "GlobalMarkets": {
                "Europa": {"momentum_1m": -5.0},
                "China": {"momentum_1m": -6.0},
                "Japon": {"momentum_1m": 1.0},
                "Asia_EM": {"momentum_1m": 0.5},
            },
        }
        engine = DecisionEngine(data, MarketStatus.HEALTHY, [])
        weak_adj, weak_reasons = engine._global_markets_adjustment()
        data["GlobalMarkets"]["Europa"]["momentum_1m"] = 5.0
        data["GlobalMarkets"]["China"]["momentum_1m"] = 5.0
        strong_adj, strong_reasons = DecisionEngine(data, MarketStatus.HEALTHY, [])._global_markets_adjustment()
        self.assertLess(weak_adj, 0)
        self.assertGreater(strong_adj, 0)
        self.assertTrue(any("presión global" in reason for reason in weak_reasons))
        self.assertTrue(any("soporte global" in reason for reason in strong_reasons))


if __name__ == "__main__":
    unittest.main()
