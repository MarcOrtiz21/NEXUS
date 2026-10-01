import json
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from risk_filters import fomc_calendar
from risk_filters.fomc_calendar import (
    FOMC_SOURCE,
    clear_fomc_cache,
    decision_datetime,
    fomc_decision_dates,
    parse_fomc_calendar,
)


def _meeting(month: str, days: str) -> str:
    return (
        '<div class="row fomc-meeting">'
        f'<div class="fomc-meeting__month col-xs-5"><strong>{month}</strong></div>\n'
        f'<div class="fomc-meeting__date col-xs-4">{days}</div>'
        "</div>"
    )


SYNTHETIC_PAGE = (
    '<h4><a id="1">2031 FOMC Meetings</a></h4>'
    + _meeting("January", "28-29")
    + _meeting("Apr/May", "30-1*")
    + _meeting("June", "10 (unscheduled)")
    + _meeting("October", "notation vote")
    + '<h4><a id="2">2030 FOMC Meetings</a></h4>'
    + _meeting("Dec", "10-11")
)


class FomcCalendarParserTests(unittest.TestCase):
    def test_decision_is_last_meeting_day_and_skips_unscheduled(self):
        self.assertEqual(
            parse_fomc_calendar(SYNTHETIC_PAGE),
            [date(2030, 12, 11), date(2031, 1, 29), date(2031, 5, 1)],
        )

    def test_decision_time_is_two_pm_eastern(self):
        self.assertEqual(
            decision_datetime(date(2031, 1, 29)),
            datetime(2031, 1, 29, 19, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(
            decision_datetime(date(2031, 7, 30)),
            datetime(2031, 7, 30, 18, 0, tzinfo=timezone.utc),
        )


class FomcCalendarCacheTests(unittest.TestCase):
    def setUp(self):
        clear_fomc_cache()
        self.tmp = tempfile.TemporaryDirectory()
        self.cache_path = Path(self.tmp.name) / "fomc.json"
        self.now = datetime(2031, 1, 20, 12, 0, tzinfo=timezone.utc)

    def tearDown(self):
        clear_fomc_cache()
        self.tmp.cleanup()

    def _session(self, text=None, error=None):
        session = MagicMock()
        if error is not None:
            session.get.side_effect = error
        else:
            session.get.return_value.text = text
            session.get.return_value.raise_for_status = lambda: None
        return session

    def test_download_is_cached_in_memory_and_disk(self):
        session = self._session(SYNTHETIC_PAGE)
        first = fomc_decision_dates(self.now, cache_path=self.cache_path, session=session)
        second = fomc_decision_dates(self.now, cache_path=self.cache_path, session=session)
        self.assertEqual(first, second)
        self.assertEqual(session.get.call_count, 1)
        payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
        self.assertEqual(payload["source"], FOMC_SOURCE)
        self.assertIn("2031-01-29", payload["decisions"])

    def test_stale_disk_cache_is_used_when_page_fails(self):
        self.cache_path.write_text(json.dumps({
            "captured_at": "2020-01-01T00:00:00+00:00",
            "decisions": ["2031-01-29"],
        }), encoding="utf-8")
        session = self._session(error=OSError("offline"))
        dates = fomc_decision_dates(self.now, cache_path=self.cache_path, session=session)
        self.assertEqual(dates, [date(2031, 1, 29)])

    def test_failure_without_cache_backs_off(self):
        session = self._session(error=OSError("offline"))
        self.assertEqual(fomc_decision_dates(self.now, cache_path=self.cache_path, session=session), [])
        self.assertEqual(fomc_decision_dates(self.now, cache_path=self.cache_path, session=session), [])
        self.assertEqual(session.get.call_count, 1)

    def test_page_without_meetings_is_rejected(self):
        session = self._session("<html>mantenimiento</html>")
        self.assertEqual(fomc_decision_dates(self.now, cache_path=self.cache_path, session=session), [])
        self.assertFalse(self.cache_path.exists())

    def test_events_inside_window_block_signals(self):
        original = fomc_calendar.fomc_decision_dates
        fomc_calendar.fomc_decision_dates = lambda now: [date(2031, 1, 29), date(2031, 5, 1)]
        try:
            events = fomc_calendar.fetch_fomc_events(lookahead_hours=24 * 10, now=self.now)
        finally:
            fomc_calendar.fomc_decision_dates = original
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["when_utc"], "2031-01-29T19:00+00:00")
        self.assertTrue(events[0]["verified"])
        self.assertTrue(events[0]["blocks_signals"])


if __name__ == "__main__":
    unittest.main()
