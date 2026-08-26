import unittest
from unittest.mock import patch

from native_api import _block_banner, _trim_sparklines, build_native_snapshot


class NativeApiContractTests(unittest.TestCase):
    def test_snapshot_sparklines_are_trimmed_to_42_points(self):
        points = [{"date": f"day-{index}", "value": index} for index in range(60)]

        trimmed = _trim_sparklines({"AAPL": points, "broken": "not-a-list"})

        self.assertEqual(len(trimmed["AAPL"]), 42)
        self.assertEqual(trimmed["AAPL"][0]["value"], 18)
        self.assertNotIn("broken", trimmed)

    @patch("native_api.evaluate_track_record", return_value={})
    @patch("native_api.summarize_paper_trading", return_value={"benchmark_valid": True})
    @patch("native_api.load_history_period", return_value=[])
    @patch("native_api.load_history_jsonl", return_value=[])
    @patch("native_api.compare_to_prior", return_value={
        "asset_ranking": [{"ticker": "SPY"}],
        "attribution": {"score": {"delta": 1}},
    })
    @patch("native_api.summarize_history")
    @patch("native_api.forex_bidirectional_rates", return_value={})
    @patch("native_api.forex_dual_perspective", return_value={})
    @patch("native_api.forex_signal", return_value={})
    @patch("native_api.analyze_news_items", return_value={})
    @patch("native_api.build_snapshot")
    def test_exposes_history_ranking_attribution_and_news_linkage(
        self,
        build_snapshot,
        _sentiment,
        _fx_signal,
        _dual,
        _rates,
        summarize_history,
        _comparison,
        _history_rows,
        _period_rows,
        _paper,
        _track,
    ):
        build_snapshot.return_value = {
            "captured_at_utc": "2026-07-23T12:00:00+00:00",
            "status_value": "HEALTHY",
            "alerts": [],
            "data": {"Assets": {}, "Forex": {}},
            "decision_dict": {},
            "news_items": [{
                "title": "Gold update",
                "linked_topics": [],
                "linked_assets": ["GLD"],
            }],
        }
        summarize_history.side_effect = lambda *args, **kwargs: {
            "period": kwargs.get("period"),
            "asset_ranking": [],
        }

        payload = build_native_snapshot()

        self.assertEqual(set(payload["history_periods"]), {"7d", "30d", "90d"})
        self.assertEqual(payload["asset_ranking"][0]["ticker"], "SPY")
        self.assertEqual(payload["change_attribution"]["score"]["delta"], 1)
        self.assertFalse(payload["news"]["linkage"]["causal"])
        self.assertEqual(payload["news"]["items"][0]["linked_assets"], ["GLD"])
        self.assertIn("session_digest", payload)
        self.assertFalse(payload["session_digest"]["has_prior"])
        self.assertIn("fx_digest", payload)
        self.assertFalse(payload["fx_digest"]["has_prior"])
        self.assertIn("fx_upcoming", payload["calendar"])
        self.assertIn("rotation_alignment", payload)
        self.assertFalse(payload["rotation_alignment"]["conflict"])
        self.assertIn("fx_alignment", payload)
        self.assertFalse(payload["fx_alignment"]["conflict"])
        self.assertIn("headlines", payload["forex"])
        self.assertIn("plan", payload["forex"])
        self.assertIn("session_plan", payload)
        self.assertEqual(payload["session_plan"]["stance"], "ESPERAR")
        self.assertEqual(payload["session_plan"]["buy_label"], "AHORA")
        self.assertIn("confidence", payload["session_plan"])
        self.assertIn("score_drivers", payload["session_plan"])
        self.assertIn("freshness", payload)
        self.assertIn("headline", payload["freshness"])
        self.assertIn("track_thesis", payload["intelligence"])
        self.assertIn("strength", payload["forex"])
        self.assertEqual(payload["forex"]["plan"]["stance"], "ESPERAR")
        self.assertEqual(payload["forex"]["headlines"][0]["linked_assets"], ["GLD"])
        self.assertIn("watchlist", payload)
        self.assertIn("sparklines", payload)
        self.assertIn("calendar_block_hours", payload["settings"])
        self.assertIn("macos_notifications", payload["settings"])
        self.assertIn("signal", payload["gold"])
        self.assertIn(payload["gold"]["signal"]["bias"], {"REFUGIO", "PRESION", "MIXTO"})
        self.assertIn("cesto", payload["news"]["linkage"]["note"])

    def test_estimated_calendar_banner_uses_approximate_window(self):
        estimated = _block_banner(
            {
                "should_block_signals": True,
                "block_hours": 6,
                "time_quality": "aproximada",
                "source": "myfxbook_rss",
                "next_event": {
                    "title": "US CPI m/m",
                    "when_utc": "2026-08-26T12:30:00+00:00",
                    "hours_until": 2,
                },
            },
            "BLOCKED",
            {"operational_action": "ESPERAR"},
        )
        self.assertTrue(estimated["estimated"])
        self.assertIn("aproximada", estimated["title"].lower())
        self.assertIn("aproximada", estimated["guidance"].lower())

        official = _block_banner(
            {
                "should_block_signals": True,
                "block_hours": 6,
                "time_quality": "oficial",
                "source": "fred_release",
                "next_event": {"title": "FOMC Statement", "hours_until": 1},
            },
            "BLOCKED",
            {},
        )
        self.assertFalse(official["estimated"])
        self.assertIn("Riesgo activo", official["title"])


if __name__ == "__main__":
    unittest.main()
