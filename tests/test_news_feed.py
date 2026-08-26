import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from risk_filters.news_feed import (
    _diversify_by_source,
    _enrich_item_context,
    _fetch_newsapi_items,
    fetch_news_items,
    fx_gold_headlines,
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
        self.assertIn("Fed/tipos", item["event_topics"])
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
    @patch("risk_filters.news_feed.requests.get")
    def test_rss_preserves_summary_and_description(self, get, parser, _api):
        response = Mock()
        response.content = b"<rss/>"
        response.raise_for_status.return_value = None
        get.return_value = response
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

    def test_fx_gold_headlines_keeps_three_tagged_stories(self):
        items = [
            {"title": "S&P 500 update", "source": "Wire"},
            {"title": "ECB keeps rates unchanged", "source": "Reuters", "url": "https://example.test/ecb"},
            {"title": "Gold rises after Fed decision", "source": "CNBC", "url": "https://example.test/gold"},
            {"title": "Dollar index climbs on payrolls", "source": "FT", "url": "https://example.test/dxy"},
            {"title": "Another gold bounce", "source": "CNBC"},
        ]
        headlines = fx_gold_headlines(items)
        self.assertEqual(len(headlines), 3)
        self.assertEqual(
            [row["title"] for row in headlines],
            [
                "ECB keeps rates unchanged",
                "Gold rises after Fed decision",
                "Dollar index climbs on payrolls",
            ],
        )
        self.assertIn("EURUSD", headlines[0]["linked_assets"])
        self.assertIn("GLD", headlines[1]["linked_assets"])
        self.assertIn("UUP", headlines[2]["linked_assets"])

    def test_links_company_names_and_keeps_earnings_out_of_event_topics(self):
        moderna = _enrich_item_context({
            "title": "Moderna reports quarterly earnings and revenue beat",
            "summary": "MRNA shares react to guidance.",
        })
        self.assertIn("MRNA", moderna["linked_companies"])
        self.assertIn("Resultados", moderna["linked_topics"])
        self.assertNotIn("Resultados", moderna["event_topics"])
        self.assertEqual(moderna["event_topics"], [])

        fed = _enrich_item_context({"title": "Fed signals another rate hold after CPI"})
        self.assertIn("Fed/tipos", fed["event_topics"])
        self.assertIn("Inflación", fed["event_topics"])

        ai = _enrich_item_context({"title": "Chip stocks rally on artificial intelligence demand"})
        self.assertIn("IA/tecnología", ai["linked_topics"])
        self.assertNotIn("IA/tecnología", ai["event_topics"])


if __name__ == "__main__":
    unittest.main()
