import unittest

from risk_filters.sentiment import analyze_headlines, analyze_news_items


class SentimentRegressionTests(unittest.TestCase):
    def test_update_does_not_trigger_bullish_up(self):
        result = analyze_headlines(["Market update shows steady trading"])
        self.assertEqual(result["dominant_sentiment"], "NEUTRAL")
        self.assertEqual(result["bull_hits"], 0)

    def test_supply_does_not_trigger_panic_down(self):
        result = analyze_headlines(["Oil supply chain remains stable"])
        self.assertEqual(result["dominant_sentiment"], "NEUTRAL")
        self.assertEqual(result["panic_hits"], 0)

    def test_panic_headline_detected(self):
        result = analyze_headlines(["Markets crash amid recession fears"])
        self.assertIn(result["dominant_sentiment"], {"PANIC", "MIXED"})
        self.assertGreater(result["panic_hits"], 0)

    def test_weighted_news_items_respect_source_weight(self):
        heavy = [{"title": "Markets crash amid recession fears", "weight": 3.0}]
        light = [{"title": "Markets crash amid recession fears", "weight": 0.2}]
        heavy_result = analyze_news_items(heavy)
        light_result = analyze_news_items(light)
        self.assertGreater(heavy_result["panic_hits"], light_result["panic_hits"])


if __name__ == "__main__":
    unittest.main()
