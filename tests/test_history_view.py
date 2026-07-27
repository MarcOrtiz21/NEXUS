import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from history_view import (
    compare_to_prior,
    downsample_rows,
    load_history_period,
    summarize_history,
)


def _row(day: datetime, score: int, spy_score: int, action: str = "MANTENER"):
    return {
        "captured_at": day.isoformat(),
        "score": score,
        "action": action,
        "operational_action": action,
        "market_status": "HEALTHY",
        "prices": {"SPY": 100 + score},
        "asset_scores": {
            "SPY": {"label": "S&P 500", "score": spy_score, "action": action},
            "GLD": {"label": "Oro", "score": 100 - spy_score, "action": "MANTENER"},
        },
        "rationale": f"score {score}",
    }


class HistoryPeriodTests(unittest.TestCase):
    def test_periods_anchor_to_latest_and_downsample_is_bounded(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        rows = [_row(start + timedelta(days=day), 50 + day, 40 + day) for day in range(100)]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.jsonl"
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

            seven_days = load_history_period("7d", path)
            summary = summarize_history(period="90d", path=path, max_points=12)

        self.assertEqual(len(seven_days), 8)
        self.assertEqual(summary["source_count"], 91)
        self.assertEqual(len(summary["score_timeline"]), 12)
        self.assertTrue(summary["downsampled"])
        self.assertEqual(summary["score_timeline"][0]["captured_at"], rows[9]["captured_at"])
        self.assertEqual(summary["score_timeline"][-1]["captured_at"], rows[-1]["captured_at"])

    def test_comparison_exposes_ranking_and_descriptive_attribution(self):
        now = datetime(2026, 7, 23, tzinfo=timezone.utc)
        prior = _row(now, 60, 40)
        latest = _row(now + timedelta(hours=1), 67, 70, action="COMPRAR")
        latest["market_status"] = "CAUTION"

        comparison = compare_to_prior([prior, latest])

        spy = next(item for item in comparison["asset_ranking"] if item["ticker"] == "SPY")
        self.assertEqual(spy["score_delta"], 30.0)
        self.assertEqual(spy["rank_delta"], 1)
        self.assertEqual(comparison["attribution"]["score"]["delta"], 7.0)
        self.assertTrue(comparison["attribution"]["action"]["changed"])
        self.assertEqual(comparison["attribution"]["top_asset_movers"][0]["ticker"], "SPY")
        self.assertIn("no implica causalidad", comparison["attribution"]["note"])

    def test_downsample_rejects_invalid_bound(self):
        with self.assertRaises(ValueError):
            downsample_rows([{}], max_points=1)


if __name__ == "__main__":
    unittest.main()
