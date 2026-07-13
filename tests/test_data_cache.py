import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from data_ingestion import (
    FAST_CACHE_KEYS,
    SLOW_CACHE_KEYS,
    _extract_tier_payload,
    _fast_cache_usable,
    _slow_cache_usable,
)


class TieredCacheTests(unittest.TestCase):
    def test_fast_cache_requires_vix_and_spy(self):
        fresh = {"_cache_age_seconds": 10, "VIX": 15.0, "Assets": {"SPY": {"price": 500.0}}}
        self.assertTrue(_fast_cache_usable(fresh))
        self.assertFalse(_fast_cache_usable({"_cache_age_seconds": 10, "VIX": 15.0}))

    def test_slow_cache_requires_macro_key(self):
        fresh = {"_cache_age_seconds": 100, "M2_Change_Pct": 1.2}
        self.assertTrue(_slow_cache_usable(fresh))
        self.assertFalse(_slow_cache_usable({"_cache_age_seconds": 100}))

    def test_extract_tier_payload_filters_empty(self):
        data = {"VIX": 14.0, "US10Y": None, "Assets": {"SPY": {"price": 1.0}}}
        payload = _extract_tier_payload(data, FAST_CACHE_KEYS)
        self.assertIn("VIX", payload)
        self.assertNotIn("US10Y", payload)


if __name__ == "__main__":
    unittest.main()
