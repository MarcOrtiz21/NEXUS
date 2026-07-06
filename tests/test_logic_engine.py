import unittest
from unittest.mock import patch

from logic_engine import LogicEngine, MarketStatus


NO_CALENDAR_EVENT = {
    "event_imminent": False,
    "should_block_signals": False,
    "events": [],
    "source": "test",
    "confidence": "HIGH",
}


class LogicEngineTests(unittest.TestCase):
    @patch("logic_engine.check_macro_events", return_value=NO_CALENDAR_EVENT)
    def test_incomplete_core_data_does_not_report_healthy(self, _mock_calendar):
        data = {
            "VIX": 14.0,
            "US10Y": None,
            "Correlation_Proxy": None,
        }

        status, alerts = LogicEngine(data, headlines=[]).evaluate()

        self.assertEqual(status, MarketStatus.UNKNOWN)
        self.assertTrue(any("DATOS CRÍTICOS INCOMPLETOS" in alert for alert in alerts))

    @patch("logic_engine.check_macro_events", return_value=NO_CALENDAR_EVENT)
    def test_minimum_core_data_can_report_healthy(self, _mock_calendar):
        data = {
            "VIX": 14.0,
            "US10Y": 4.1,
            "Correlation_Proxy": None,
        }

        status, _alerts = LogicEngine(data, headlines=[]).evaluate()

        self.assertEqual(status, MarketStatus.HEALTHY)

    @patch("logic_engine.check_macro_events", return_value=NO_CALENDAR_EVENT)
    def test_panic_signal_overrides_incomplete_supporting_data(self, _mock_calendar):
        data = {
            "VIX": 35.0,
            "VIX_MA5": 20.0,
            "US10Y": None,
            "Correlation_Proxy": None,
        }

        status, alerts = LogicEngine(data, headlines=[]).evaluate()

        self.assertEqual(status, MarketStatus.PANIC)
        self.assertTrue(any("PÁNICO EXTREMO" in alert for alert in alerts))


if __name__ == "__main__":
    unittest.main()
