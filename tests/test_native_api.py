import unittest
from unittest.mock import patch

from native_api import build_native_snapshot


class NativeApiContractTests(unittest.TestCase):
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
    @patch("native_api.check_macro_events", return_value={})
    @patch("native_api.build_snapshot")
    def test_exposes_history_ranking_attribution_and_news_linkage(
        self,
        build_snapshot,
        _calendar,
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


if __name__ == "__main__":
    unittest.main()
