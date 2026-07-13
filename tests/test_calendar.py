import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from risk_filters.calendar import (
    _is_us_blocking_event,
    _is_us_event,
    check_macro_events,
)


class CalendarRegressionTests(unittest.TestCase):
    def test_mauritius_does_not_match_us(self):
        self.assertFalse(_is_us_event("Mauritius CPI m/m"))
        self.assertFalse(_is_us_blocking_event("Mauritius CPI m/m"))

    def test_us_cpi_is_blocking(self):
        self.assertTrue(_is_us_event("US CPI m/m"))
        self.assertTrue(_is_us_blocking_event("US CPI m/m"))

    def test_fomc_is_us_blocking(self):
        self.assertTrue(_is_us_blocking_event("FOMC Statement"))

    def test_manual_fallback_does_not_block(self):
        as_of = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
        with patch("risk_filters.calendar.get_setting", side_effect=lambda key: {"calendar_blocks_signals": True, "calendar_block_hours": 6}.get(key, True)):
            result = check_macro_events(as_of=as_of, block_hours=6)
        manual = [event for event in result["events_detail"] if event.get("source") == "estimado_manual"]
        self.assertTrue(manual)
        self.assertFalse(result["should_block_signals"])

    def test_verified_us_blocking_event_blocks_within_window(self):
        as_of = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)
        event_time = datetime(2026, 7, 14, 14, 0, tzinfo=timezone.utc)
        fake_event = {
            "title": "US CPI m/m",
            "when_utc": event_time.isoformat(timespec="minutes"),
            "hours_until": 4.0,
            "impact": "ALTO",
            "source": "myfxbook_rss",
            "verified": True,
            "us_event": True,
            "blocks_signals": True,
        }

        from unittest.mock import patch

        with patch("risk_filters.calendar._fetch_rss_events", return_value=[fake_event]):
            with patch("risk_filters.calendar._manual_fallback_events", return_value=[]):
                with patch("risk_filters.calendar.get_setting", side_effect=lambda key: {"calendar_blocks_signals": True, "calendar_block_hours": 6}.get(key, True)):
                    result = check_macro_events(as_of=as_of, block_hours=6)

        self.assertTrue(result["should_block_signals"])
        self.assertEqual(len(result["blocking_events"]), 1)


if __name__ == "__main__":
    unittest.main()
