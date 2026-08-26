import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from data_ingestion import (
    CACHE_SCHEMA_VERSION,
    FAST_CACHE_KEYS,
    ROTATION_CACHE_KEYS,
    SLOW_CACHE_KEYS,
    _apply_cache_fallback,
    _extract_tier_payload,
    _find_obs_near_date,
    _fast_cache_usable,
    _rotation_cache_usable,
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

    def test_fast_cache_does_not_require_company_detail(self):
        fresh = {
            "_cache_age_seconds": 10,
            "schema_version": CACHE_SCHEMA_VERSION,
            "VIX": 15.0,
            "Assets": {"SPY": {"price": 500.0}, "GLD": {"price": 200.0}},
            "Forex": {"EURUSD": {"price": 1.08}},
            "GlobalMarkets": {"Europa": {"price": 40.0}},
        }
        self.assertTrue(_fast_cache_usable(fresh))

    def test_rotation_cache_requires_company_price(self):
        fresh = {
            "_cache_age_seconds": 10,
            "schema_version": CACHE_SCHEMA_VERSION,
            "RotationCompanies": {"LMT": {"price": 500.0}},
        }
        self.assertTrue(_rotation_cache_usable(fresh))
        self.assertFalse(_rotation_cache_usable({**fresh, "RotationCompanies": {}}))
        self.assertEqual(ROTATION_CACHE_KEYS, ("RotationCompanies",))

    def test_older_rotation_schema_still_opens_the_app(self):
        stale = {
            "_cache_age_seconds": 60 * 60,
            "schema_version": 6,
            "RotationCompanies": {"AAPL": {"price": 210.0}},
        }
        from data_ingestion import _rotation_cache_complete
        self.assertTrue(_rotation_cache_complete(stale))
        self.assertFalse(_rotation_cache_usable(stale))

    def test_slow_cache_requires_macro_key(self):
        fresh = {"_cache_age_seconds": 100, "schema_version": CACHE_SCHEMA_VERSION, "M2_Change_Pct": 1.2}
        self.assertTrue(_slow_cache_usable(fresh))
        self.assertFalse(_slow_cache_usable({"_cache_age_seconds": 100, "schema_version": CACHE_SCHEMA_VERSION}))
        self.assertFalse(_slow_cache_usable({"_cache_age_seconds": 100, "M2_Change_Pct": 1.2}))

    def test_stale_cache_is_complete_enough_to_open_the_app(self):
        stale = {
            "_cache_age_seconds": 60 * 60 * 24,
            "schema_version": CACHE_SCHEMA_VERSION,
            "VIX": 15.0,
            "Assets": {"SPY": {"price": 500.0}, "GLD": {"price": 200.0}},
            "Forex": {"EURUSD": {"price": 1.08}},
            "GlobalMarkets": {"Europa": {"price": 40.0}},
        }
        self.assertFalse(_fast_cache_usable(stale))
        from data_ingestion import _fast_cache_complete
        self.assertTrue(_fast_cache_complete(stale))

    def test_yf_timeout_keeps_stale_cache(self):
        import pandas as pd
        from data_ingestion import _sparkline_points

        series = pd.Series([100.0, 102.0, 101.0], index=pd.date_range("2026-08-01", periods=3, freq="D"))
        spy = pd.Series([200.0, 200.0, 198.0], index=series.index)
        points = _sparkline_points(series, spy, points=3)
        self.assertEqual(len(points), 3)
        self.assertEqual(points[0]["date"], "2026-08-01")
        self.assertIsNotNone(points[-1]["rel_spy"])

    def test_sparkline_horizon_covers_about_one_year(self):
        from data_ingestion import SPARKLINE_POINTS
        self.assertEqual(SPARKLINE_POINTS, 252)

    def test_ohlc_sparkline_keeps_range_and_ma20(self):
        import pandas as pd
        from data_ingestion import _ohlc_sparkline_points

        idx = pd.date_range("2026-01-05", periods=25, freq="B")
        close = pd.Series([180 + i * 0.4 for i in range(25)], index=idx)
        frame = pd.concat(
            {
                "Open": pd.DataFrame({"GLD": close.shift(1).fillna(close.iloc[0])}),
                "High": pd.DataFrame({"GLD": close + 1.5}),
                "Low": pd.DataFrame({"GLD": close - 1.2}),
                "Close": pd.DataFrame({"GLD": close, "SPY": close * 2}),
            },
            axis=1,
        )
        points = _ohlc_sparkline_points(frame, "GLD", spy=close * 2, points=25, decimals=2)
        self.assertEqual(len(points), 25)
        self.assertGreater(points[-1]["high"], points[-1]["value"])
        self.assertLess(points[-1]["low"], points[-1]["value"])
        self.assertIsNotNone(points[-1]["ma20"])
        self.assertIsNotNone(points[-1]["rel_spy"])

    def test_ohlc_sparklines_cover_rotation_and_decision_assets(self):
        import pandas as pd
        from data_ingestion import _build_ohlc_sparklines

        idx = pd.date_range("2026-01-05", periods=25, freq="B")
        close = pd.Series([100 + i * 0.2 for i in range(25)], index=idx)
        tickers = ["IGV", "SPY", "QQQ", "GLD"]
        bases = {ticker: close + offset for ticker, offset in zip(tickers, (0, 1, -0.5, 80))}
        frame = pd.concat(
            {
                "Open": pd.DataFrame({key: series - 0.3 for key, series in bases.items()}),
                "High": pd.DataFrame({key: series + 1.2 for key, series in bases.items()}),
                "Low": pd.DataFrame({key: series - 1.1 for key, series in bases.items()}),
                "Close": pd.DataFrame(bases),
            },
            axis=1,
        )
        close_frame = frame["Close"]
        charts = _build_ohlc_sparklines(frame, close_frame, tickers=tickers)
        self.assertIn("IGV", charts)
        self.assertIn("SPY", charts)
        self.assertGreater(charts["IGV"][-1]["high"], charts["IGV"][-1]["value"])
        self.assertIsNotNone(charts["IGV"][-1]["ma20"])

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

    def test_refresh_false_skips_yahoo_when_disk_cache_is_complete(self):
        from data_ingestion import (
            FAST_MARKET_CACHE_FILE,
            ROTATION_MARKET_CACHE_FILE,
            SLOW_MACRO_CACHE_FILE,
            fetch_market_data,
        )

        fast = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "_cache_age_seconds": 60 * 60 * 24,
            "VIX": 15.0,
            "US10Y": 4.2,
            "Assets": {"SPY": {"price": 500.0}, "GLD": {"price": 200.0}},
            "Forex": {"EURUSD": {"price": 1.08}},
            "GlobalMarkets": {"Europa": {"price": 40.0}},
        }
        rotation = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "_cache_age_seconds": 60 * 60 * 24,
            "RotationCompanies": {"AAPL": {"price": 210.0}},
        }
        slow = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "_cache_age_seconds": 60 * 60 * 24,
            "M2_Change_Pct": 1.2,
            "PE_Trailing": 22.0,
        }

        def load_tier(path):
            if path == FAST_MARKET_CACHE_FILE:
                return fast
            if path == ROTATION_MARKET_CACHE_FILE:
                return rotation
            if path == SLOW_MACRO_CACHE_FILE:
                return slow
            return {}

        with patch("data_ingestion._load_market_cache", return_value={}):
            with patch("data_ingestion._load_tier_cache", side_effect=load_tier):
                with patch("data_ingestion._yf_download") as yf:
                    with patch("data_ingestion._fetch_sp500_pe") as pe:
                        with patch("data_ingestion._fetch_siblis_forward_pe") as siblis:
                            with patch("data_ingestion._save_market_cache"):
                                with patch("data_ingestion._save_tier_cache"):
                                    data = fetch_market_data(refresh=False)

        yf.assert_not_called()
        pe.assert_not_called()
        siblis.assert_not_called()
        self.assertEqual(data["VIX"], 15.0)
        self.assertEqual(data["RotationCompanies"]["AAPL"]["price"], 210.0)
        self.assertEqual(data["M2_Change_Pct"], 1.2)
        self.assertEqual(data["Freshness"]["market"]["status"], "STALE")
        self.assertEqual(data["Freshness"]["macro"]["status"], "STALE")
        self.assertEqual(data["Freshness"]["companies"]["status"], "STALE")

    def test_refresh_skips_company_yahoo_when_older_rotation_cache_exists(self):
        from data_ingestion import (
            FAST_MARKET_CACHE_FILE,
            ROTATION_MARKET_CACHE_FILE,
            SLOW_MACRO_CACHE_FILE,
            fetch_market_data,
        )

        fast = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "_cache_age_seconds": 60,
            "VIX": 15.0,
            "US10Y": 4.2,
            "Assets": {"SPY": {"price": 500.0}, "GLD": {"price": 200.0}},
            "Forex": {"EURUSD": {"price": 1.08}},
            "GlobalMarkets": {"Europa": {"price": 40.0}},
        }
        rotation = {
            "schema_version": 6,
            "_cache_age_seconds": 60 * 60,
            "RotationCompanies": {"AAPL": {"price": 210.0}},
        }
        slow = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "_cache_age_seconds": 10,
            "M2_Change_Pct": 1.2,
            "PE_Trailing": 22.0,
        }

        def load_tier(path):
            if path == FAST_MARKET_CACHE_FILE:
                return fast
            if path == ROTATION_MARKET_CACHE_FILE:
                return rotation
            if path == SLOW_MACRO_CACHE_FILE:
                return slow
            return {}

        with patch("data_ingestion._load_market_cache", return_value={}):
            with patch("data_ingestion._load_tier_cache", side_effect=load_tier):
                with patch("data_ingestion._yf_download") as yf:
                    with patch("data_ingestion._fetch_sp500_pe") as pe:
                        with patch("data_ingestion._fetch_siblis_forward_pe") as siblis:
                            with patch("data_ingestion._save_market_cache"):
                                with patch("data_ingestion._save_tier_cache"):
                                    with patch("data_ingestion._fetch_latest_fred_value") as fred:
                                        with patch("data_ingestion._fetch_fred_series") as fred_series:
                                            data = fetch_market_data(refresh=True)

        self.assertEqual(data["RotationCompanies"]["AAPL"]["price"], 210.0)
        self.assertEqual(data["M2_Change_Pct"], 1.2)
        self.assertEqual(data["Freshness"]["market"]["status"], "OK")
        self.assertEqual(data["Freshness"]["macro"]["status"], "OK")
        self.assertEqual(data["Freshness"]["companies"]["status"], "STALE")
        pe.assert_not_called()
        siblis.assert_not_called()
        fred.assert_not_called()
        fred_series.assert_not_called()
        for call in yf.call_args_list:
            tickers = call.args[0] if call.args else call.kwargs.get("tickers") or []
            self.assertNotIn("AAPL", tickers)

    def test_payload_age_uses_captured_at_not_mtime(self):
        from datetime import datetime, timedelta, timezone
        from data_ingestion import _payload_age_seconds

        stamp = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat(timespec="seconds")
        age = _payload_age_seconds({"captured_at": stamp}, mtime_age=8)
        self.assertAlmostEqual(age, 3 * 3600, delta=5)
        self.assertEqual(_payload_age_seconds({}, 12.0), 12.0)

    def test_cross_sanity_rejects_absurd_prints(self):
        from data_ingestion import _apply_cross_sanity

        data = {
            "VIX": 140.0,
            "VIX_MA5": 30.0,
            "Assets": {"SPY": {"price": 500.0}},
            "Forex": {"EURUSD": {"price": 1.10}},
            "CrossPrices": {"IVV": 400.0, "USDEUR": 0.70},
            "DataQuality": {},
        }
        rejected = _apply_cross_sanity(data)
        self.assertIn("VIX", rejected)
        self.assertIsNone(data["VIX"])
        self.assertIsNone(data["VIX_MA5"])
        self.assertIn("SPY", rejected)
        self.assertIsNone(data["Assets"]["SPY"]["price"])
        self.assertIn("EURUSD", rejected)
        self.assertIsNone(data["Forex"]["EURUSD"]["price"])
        self.assertIn("saneamiento", data["DataQuality"]["VIX"]["detail"])

    def test_cross_sanity_keeps_aligned_prints(self):
        from data_ingestion import _apply_cross_sanity

        data = {
            "VIX": 16.0,
            "Assets": {"SPY": {"price": 500.0}},
            "Forex": {"EURUSD": {"price": 1.10}},
            "CrossPrices": {"IVV": 501.0, "USDEUR": 0.909},
            "DataQuality": {},
        }
        self.assertEqual(_apply_cross_sanity(data), [])
        self.assertEqual(data["VIX"], 16.0)
        self.assertEqual(data["Assets"]["SPY"]["price"], 500.0)

    def test_refresh_does_not_rewrite_slow_or_rotation_when_reused(self):
        from data_ingestion import (
            FAST_MARKET_CACHE_FILE,
            ROTATION_MARKET_CACHE_FILE,
            SLOW_MACRO_CACHE_FILE,
            fetch_market_data,
        )

        fast = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "_cache_age_seconds": 60,
            "VIX": 15.0,
            "US10Y": 4.2,
            "Assets": {"SPY": {"price": 500.0}, "GLD": {"price": 200.0}},
            "Forex": {"EURUSD": {"price": 1.08}},
            "GlobalMarkets": {"Europa": {"price": 40.0}},
        }
        rotation = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "_cache_age_seconds": 60,
            "RotationCompanies": {"AAPL": {"price": 210.0}},
        }
        slow = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "_cache_age_seconds": 10,
            "M2_Change_Pct": 1.2,
            "CPI_YoY_Pct": 2.4,
            "CPI_AsOf": "2026-07-15",
            "PE_Trailing": 22.0,
        }

        def load_tier(path):
            if path == FAST_MARKET_CACHE_FILE:
                return fast
            if path == ROTATION_MARKET_CACHE_FILE:
                return rotation
            if path == SLOW_MACRO_CACHE_FILE:
                return slow
            return {}

        saved = []

        def capture_save(path, payload, **kwargs):
            saved.append(path)

        with patch("data_ingestion._load_market_cache", return_value={}):
            with patch("data_ingestion._load_tier_cache", side_effect=load_tier):
                with patch("data_ingestion._yf_download") as yf:
                    with patch("data_ingestion._fetch_sp500_pe"):
                        with patch("data_ingestion._fetch_siblis_forward_pe"):
                            with patch("data_ingestion._save_market_cache"):
                                with patch("data_ingestion._save_tier_cache", side_effect=capture_save):
                                    with patch("data_ingestion._fetch_latest_fred_value"):
                                        with patch("data_ingestion._fetch_fred_series"):
                                            data = fetch_market_data(refresh=True)

        self.assertEqual(data["M2_Change_Pct"], 1.2)
        self.assertEqual(data["DataQuality"]["CPI_YoY_Pct"]["as_of"], "2026-07-15")
        self.assertNotIn(SLOW_MACRO_CACHE_FILE, saved)
        self.assertNotIn(ROTATION_MARKET_CACHE_FILE, saved)
        for call in yf.call_args_list:
            tickers = call.args[0] if call.args else call.kwargs.get("tickers") or []
            self.assertNotIn("AAPL", tickers)


if __name__ == "__main__":
    unittest.main()
