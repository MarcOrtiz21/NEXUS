import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from risk_filters.calendar import check_macro_events, fx_gold_upcoming_events
from risk_filters.ecb_calendar import (
    ECB_SOURCE,
    decision_datetime,
    fetch_ecb_events,
    parse_ecb_calendar,
)


def _entry(day: str, description: str) -> str:
    return f"<dt> \n{day}\n</dt>\n<dd>\n{description}<br>\n</dd>\n"


SYNTHETIC_PAGE = (
    '<div class="definition-list -zebra"><dl>'
    + _entry("20/01/2031", "Governing Council of the ECB: monetary policy meeting in Frankfurt (Day 1)")
    + _entry("21/01/2031", "Governing Council of the ECB: monetary policy meeting in Frankfurt (Day 2), followed by press conference")
    + _entry("05/02/2031", "Governing Council of the ECB: non-monetary policy meeting (virtual)")
    + _entry("06/02/2031", "General Council meeting of the ECB in Frankfurt")
    + _entry("12/03/2031", "Governing Council of the ECB: monetary policy meeting in Vienna, followed by press conference")
    + _entry("15/04/2031", "Governing Council of the ECB: monetary policy meeting in Frankfurt")
    + _entry("16/04/2031", "Governing Council of the ECB: monetary policy meeting in Frankfurt (Day 2), followed by press conference")
    + "</dl></div>"
)


class EcbCalendarTests(unittest.TestCase):
    def test_only_monetary_policy_decision_days_are_kept(self):
        self.assertEqual(parse_ecb_calendar(SYNTHETIC_PAGE), [date(2031, 1, 21), date(2031, 3, 12), date(2031, 4, 16)])

    def test_decision_time_is_quarter_past_two_in_frankfurt(self):
        self.assertEqual(decision_datetime(date(2031, 1, 21)), datetime(2031, 1, 21, 13, 15, tzinfo=timezone.utc))
        self.assertEqual(decision_datetime(date(2031, 7, 24)), datetime(2031, 7, 24, 12, 15, tzinfo=timezone.utc))

    def test_ecb_event_is_shown_for_fx_gold_but_never_blocks(self):
        now = datetime(2031, 1, 20, 12, 0, tzinfo=timezone.utc)
        with patch("risk_filters.ecb_calendar.ecb_decision_dates", return_value=[date(2031, 1, 21)]):
            events = fetch_ecb_events(lookahead_hours=48, now=now)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["source"], ECB_SOURCE)
        self.assertFalse(events[0]["blocks_signals"])

        with patch("risk_filters.calendar.fetch_fred_release_events", return_value=[]), \
                patch("risk_filters.calendar.fetch_fomc_events", return_value=[]), \
                patch("risk_filters.calendar.fetch_ecb_events", return_value=events), \
                patch("risk_filters.calendar.get_setting", return_value=True):
            result = check_macro_events(as_of=now, block_hours=6)
        self.assertFalse(result["should_block_signals"])
        upcoming = fx_gold_upcoming_events(result["events_detail"])
        self.assertEqual([event["title"] for event in upcoming], [events[0]["title"]])
        self.assertEqual(upcoming[0]["time_quality"], "oficial")
        self.assertTrue(any(event["source"] == ECB_SOURCE for event in result["gold_events_30d"]))


if __name__ == "__main__":
    unittest.main()
