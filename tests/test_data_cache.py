import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from data_ingestion import (
    CACHE_SCHEMA_VERSION,
    FAST_CACHE_KEYS,
    SLOW_CACHE_KEYS,
    _apply_cache_fallback,
    _extract_tier_payload,
    _find_obs_near_date,
    _fast_cache_usable,
    _slow_cache_usable,
)


class TieredCacheTests(unittest.TestCase):
    def test_fast_cache_requires_market_forex_and_gold(self):
        fresh = {
            "_cache_age_seconds": 10,
            "schema_version": CACHE_SCHEMA_VERSION,
            "VIX": 15.0,
            "Assets": {"SPY": {"price": 500.0}, "GLD": {"price": 200.0}},
            "RotationCompanies": {"AAPL": {"price": 210.0}},
            "Forex": {"EURUSD": {"price": 1.08}},
            "GlobalMarkets": {"Europa": {"price": 40.0}},
        }
        self.assertTrue(_fast_cache_usable(fresh))
        self.assertFalse(_fast_cache_usable({"_cache_age_seconds": 10, "schema_version": CACHE_SCHEMA_VERSION, "VIX": 15.0}))
        missing_forex = {
            "_cache_age_seconds": 10,
            "schema_version": CACHE_SCHEMA_VERSION,
            "VIX": 15.0,
            "Assets": {"SPY": {"price": 500.0}, "GLD": {"price": 200.0}},
        }
        self.assertFalse(_fast_cache_usable(missing_forex))

    def test_slow_cache_requires_macro_key(self):
        fresh = {"_cache_age_seconds": 100, "schema_version": CACHE_SCHEMA_VERSION, "M2_Change_Pct": 1.2}
        self.assertTrue(_slow_cache_usable(fresh))
        self.assertFalse(_slow_cache_usable({"_cache_age_seconds": 100, "schema_version": CACHE_SCHEMA_VERSION}))
        self.assertFalse(_slow_cache_usable({"_cache_age_seconds": 100, "M2_Change_Pct": 1.2}))

    def test_extract_tier_payload_filters_empty(self):
        data = {"VIX": 14.0, "US10Y": None, "Assets": {"SPY": {"price": 1.0}}}
        payload = _extract_tier_payload(data, FAST_CACHE_KEYS)
        self.assertIn("VIX", payload)
        self.assertNotIn("US10Y", payload)

    def test_cache_fallback_merges_missing_metrics_without_overwriting_fresh_data(self):
        data = {
            "Assets": {
                "SPY": {"price": 501.0, "ma20": None},
                "QQQ": {"price": None, "ma20": None},
            }
        }
        cache = {
            "Assets": {
                "SPY": {"price": 499.0, "ma20": 490.0},
                "QQQ": {"price": 420.0, "ma20": 410.0},
            },
            "schema_version": CACHE_SCHEMA_VERSION,
        }

        _apply_cache_fallback(data, cache)

        self.assertEqual(data["Assets"]["SPY"]["price"], 501.0)
        self.assertEqual(data["Assets"]["SPY"]["ma20"], 490.0)
        self.assertEqual(data["Assets"]["QQQ"]["price"], 420.0)

    def test_observation_lookup_never_uses_future_value(self):
        observations = [
            {"date": "2026-01-01", "value": 100.0},
            {"date": "2026-02-01", "value": 110.0},
        ]
        self.assertEqual(_find_obs_near_date(observations, "2026-01-15"), 100.0)
        self.assertIsNone(_find_obs_near_date(observations, "2025-12-15"))


if __name__ == "__main__":
    unittest.main()
