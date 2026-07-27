import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from risk_filters.news_feed import (
    _diversify_by_source,
    _enrich_item_context,
    _fetch_newsapi_items,
    fetch_news_items,
)


class NewsFeedOrderingTests(unittest.TestCase):
    def test_diversification_interleaves_sources_before_ui_cap(self):
        items = [
            {"title": "CNBC 1", "source": "CNBC", "published_at": "2026-07-22T12:00:00+00:00"},
            {"title": "CNBC 2", "source": "CNBC", "published_at": "2026-07-22T11:00:00+00:00"},
            {"title": "Reuters 1", "source": "Reuters", "published_at": "2026-07-22T10:00:00+00:00"},
            {"title": "ECB 1", "source": "ECB", "published_at": "2026-07-22T09:00:00+00:00"},
        ]

        ordered = _diversify_by_source(items)

        self.assertEqual([row["source"] for row in ordered[:3]], ["CNBC", "Reuters", "ECB"])
        self.assertEqual(ordered[3]["title"], "CNBC 2")

    def test_cleans_text_and_links_only_explicit_context(self):
        item = _enrich_item_context({
            "title": "Gold rises after Fed decision",
            "summary": "<p>Gold &amp; bullion react.</p>",
            "description": "x" * 700,
        })

        self.assertEqual(item["summary"], "Gold & bullion react.")
        self.assertLessEqual(len(item["description"]), 600)
        self.assertEqual(item["linked_assets"], ["GLD"])
        self.assertIn("Fed/tipos", item["linked_topics"])
        self.assertIn("no implica causalidad", item["linkage_note"])

    @patch("risk_filters.news_feed.NEWSAPI_KEY", "secret")
    @patch("risk_filters.news_feed.requests.get")
    def test_newsapi_preserves_clean_description(self, get):
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"articles": [{
            "title": "S&P 500 update",
            "description": "<b>Markets</b> advance",
            "publishedAt": "2026-07-23T12:00:00Z",
            "source": {"name": "Wire"},
            "url": "https://example.test/story",
        }]}
        get.return_value = response

        item = _fetch_newsapi_items()[0]

        self.assertEqual(item["summary"], "Markets advance")
        self.assertEqual(item["description"], "Markets advance")
        self.assertEqual(item["linked_assets"], ["SPY"])

    @patch("risk_filters.news_feed._fetch_newsapi_items", return_value=[])
    @patch("risk_filters.news_feed.RSS_FEEDS", [{"name": "Feed", "url": "https://example.test/rss"}])
    @patch("risk_filters.news_feed.feedparser")
    def test_rss_preserves_summary_and_description(self, parser, _api):
        parser.parse.return_value = SimpleNamespace(entries=[{
            "title": "EUR/USD outlook",
            "link": "https://example.test/rss/1",
            "summary": "<p>Euro summary</p>",
            "description": "<div>Dollar description</div>",
        }])

        item = fetch_news_items()[0]

        self.assertEqual(item["summary"], "Euro summary")
        self.assertEqual(item["description"], "Dollar description")
        self.assertEqual(item["linked_assets"], ["EURUSD"])


if __name__ == "__main__":
    unittest.main()
