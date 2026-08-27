import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import HTTPException

from chart_series import ChartSeriesService, normalize_chart_ticker, validate_chart_request
from web_dashboard import api_native_chart


def _ohlc_frame(tickers=("AAPL", "SPY"), rows=300, freq="B", start="2025-01-01"):
    index = pd.date_range(start, periods=rows, freq=freq)
    columns = {}
    for ticker_index, ticker in enumerate(tickers):
        close = pd.Series(
            [100 + ticker_index * 20 + day for day in range(rows)],
            index=index,
            dtype=float,
        )
        columns[("Open", ticker)] = close - 1
        columns[("High", ticker)] = close + 2
        columns[("Low", ticker)] = close - 2
        columns[("Close", ticker)] = close
        columns[("Volume", ticker)] = pd.Series(
            [1000 + day for day in range(rows)], index=index, dtype=float
        )
    return pd.DataFrame(columns, index=index)


class ChartSeriesTests(unittest.TestCase):
    def test_ticker_sanitization_and_aliases(self):
        self.assertEqual(normalize_chart_ticker(" eurusd "), ("EURUSD", "EURUSD=X"))
        self.assertEqual(normalize_chart_ticker("usdeur"), ("USDEUR", "EURUSD=X"))
        self.assertEqual(normalize_chart_ticker("usdcad"), ("USDCAD", "CAD=X"))
        self.assertEqual(normalize_chart_ticker("gbpusd"), ("GBPUSD", "GBPUSD=X"))
        self.assertEqual(normalize_chart_ticker("xauusd"), ("XAUUSD", "GC=F"))
        self.assertEqual(normalize_chart_ticker("gc=f"), ("XAUUSD", "GC=F"))
        self.assertEqual(normalize_chart_ticker("^vix"), ("VIX", "^VIX"))
        self.assertEqual(normalize_chart_ticker("ssnlf"), ("SSNLF", "005930.KS"))
        self.assertEqual(normalize_chart_ticker("000660.ks"), ("000660.KS", "000660.KS"))
        with self.assertRaises(ValueError):
            normalize_chart_ticker("../../AAPL")
        with self.assertRaises(ValueError):
            normalize_chart_ticker("AAPL SPY")

    def test_interval_range_validation_is_actionable(self):
        self.assertEqual(validate_chart_request(), ("1d", "1y"))
        self.assertEqual(validate_chart_request("4H", "6MO"), ("4h", "6mo"))
        with self.assertRaisesRegex(ValueError, "Intervalo.*Usa"):
            validate_chart_request("2h", "1mo")
        with self.assertRaisesRegex(ValueError, "Rango.*Usa"):
            validate_chart_request("1d", "2y")
        with self.assertRaisesRegex(ValueError, "Yahoo no admite.*Para 1m usa"):
            validate_chart_request("1m", "1mo")

    def test_cache_is_separated_by_ticker_interval_and_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame()
            with patch("chart_series._yf_download", return_value=frame) as download:
                first = service.get("AAPL", interval="1d", range_name="6mo")
                cached = service.get("AAPL", interval="1d", range_name="6mo")
                other = service.get("AAPL", interval="1d", range_name="1y")

            self.assertEqual(download.call_count, 2)
            self.assertEqual(first["status"], "live")
            self.assertEqual(cached["status"], "fresh")
            self.assertEqual(other["range"], "1y")
            self.assertNotEqual(first["revision"], other["revision"])
            paths = list(Path(tmp).rglob("*.json"))
            self.assertEqual(len(paths), 4)
            self.assertEqual(len({path.as_posix() for path in paths}), 4)

    def test_force_refresh_bypasses_fresh_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame()
            with patch("chart_series._yf_download", return_value=frame) as download:
                service.get("AAPL")
                refreshed = service.get("AAPL", force=True)

            self.assertEqual(download.call_count, 2)
            self.assertEqual(refreshed["status"], "live")
            self.assertEqual(refreshed["source"], "yahoo_finance")
            download.assert_called_with(
                ["AAPL", "SPY"], period="2y", interval="1d"
            )

    def test_concurrent_fetch_is_deduplicated_per_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame()
            started = threading.Event()
            release = threading.Event()

            def download(*args, **kwargs):
                started.set()
                release.wait(timeout=2)
                return frame

            results = []
            with patch("chart_series._yf_download", side_effect=download) as mocked:
                first = threading.Thread(target=lambda: results.append(service.get("AAPL")))
                second = threading.Thread(target=lambda: results.append(service.get("AAPL")))
                first.start()
                self.assertTrue(started.wait(timeout=1))
                second.start()
                release.set()
                first.join(timeout=2)
                second.join(timeout=2)

            self.assertEqual(mocked.call_count, 1)
            self.assertEqual(len(results), 2)

    def test_eurusd_daily_ranges_keep_full_session_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame(("EURUSD=X", "SPY"), rows=320)
            with patch("chart_series._yf_download", return_value=frame):
                six_months = service.get("EURUSD", range_name="6mo")
                one_year = service.get("EURUSD", range_name="1y")

            self.assertEqual(len(six_months["points"]), 132)
            self.assertEqual(len(one_year["points"]), 252)
            self.assertTrue(all(point["volume"] is None for point in one_year["points"]))
            self.assertEqual(one_year["session"], "24x5")

    def test_usdeur_inverts_eurusd_ohlc_without_swapping_the_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame(("EURUSD=X", "SPY"), rows=80)
            with patch("chart_series._yf_download", return_value=frame):
                payload = service.get("USDEUR", range_name="3mo")

            first = payload["points"][0]
            self.assertEqual(payload["ticker"], "USDEUR")
            self.assertEqual(payload["session"], "24x5")
            self.assertAlmostEqual(first["close"], round(1 / 114, 5))
            self.assertAlmostEqual(first["open"], round(1 / 113, 5))
            self.assertAlmostEqual(first["high"], round(1 / 112, 5))
            self.assertAlmostEqual(first["low"], round(1 / 116, 5))
            self.assertGreater(first["high"], first["low"])

    def test_xauusd_uses_comex_gold_not_missing_fx_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame(("GC=F", "SPY"), rows=80)
            with patch("chart_series._yf_download", return_value=frame) as download:
                payload = service.get("XAUUSD", range_name="3mo")

            self.assertIn("GC=F", download.call_args[0][0])
            self.assertEqual(payload["ticker"], "XAUUSD")
            self.assertEqual(payload["session"], "regular")
            self.assertGreater(len(payload["points"]), 20)
            self.assertIsNotNone(payload["points"][-1]["close"])

    def test_samsung_otc_symbol_uses_liquid_korean_listing_for_intraday(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame(("005930.KS", "SPY"), rows=80, freq="h")
            with patch("chart_series._yf_download", return_value=frame) as download:
                payload = service.get("SSNLF", interval="1h", range_name="1mo")

            self.assertIn("005930.KS", download.call_args[0][0])
            self.assertEqual(payload["ticker"], "SSNLF")
            self.assertGreater(len(payload["points"]), 20)

    def test_xauusd_retries_gc_futures_when_fx_symbol_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            empty_fx = _ohlc_frame(("XAUUSD=X", "SPY"), rows=3)
            empty_fx.loc[:, (slice(None), "XAUUSD=X")] = float("nan")
            gold = _ohlc_frame(("GC=F",), rows=80)

            def download(tickers, period="2y", timeout=20, interval="1d"):
                if "GC=F" in tickers and "SPY" not in tickers:
                    return gold
                return empty_fx

            with patch("chart_series._yf_download", side_effect=download) as mocked:
                payload = service.get("XAUUSD", range_name="3mo")

            called = [call[0][0] for call in mocked.call_args_list]
            self.assertTrue(any("GC=F" in tickers for tickers in called))
            self.assertEqual(payload["ticker"], "XAUUSD")
            self.assertGreater(len(payload["points"]), 20)

    def test_missing_spy_does_not_block_the_requested_series(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame(("GC=F",), rows=80)
            with patch("chart_series._yf_download", return_value=frame):
                payload = service.get("XAUUSD", range_name="3mo")
            self.assertEqual(payload["ticker"], "XAUUSD")
            self.assertGreater(len(payload["points"]), 20)

    def test_ohlcv_and_metadata_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            with patch("chart_series._yf_download", return_value=_ohlc_frame()):
                payload = service.get("AAPL")

            point = payload["points"][-1]
            self.assertTrue({
                "date", "epoch", "open", "high", "low", "close", "value",
                "volume", "ma20", "ma50", "ma200", "synthetic_ohlc",
                "interval", "timezone", "session", "adjusted", "adjustment",
            }.issubset(point))
            self.assertIsInstance(point["epoch"], int)
            self.assertEqual(point["close"], point["value"])
            self.assertFalse(point["synthetic_ohlc"])
            self.assertIsNotNone(point["ma200"])
            self.assertEqual(payload["adjustment"], "unadjusted")
            self.assertIn("market_state", payload)
            self.assertIn("data_status", payload)

    def test_four_hour_bars_aggregate_hourly_ohlcv(self):
        with tempfile.TemporaryDirectory() as tmp:
            service = ChartSeriesService(cache_dir=Path(tmp), ttl_seconds=3600)
            frame = _ohlc_frame(rows=8, freq="h", start="2026-08-25 09:00")
            with patch("chart_series._yf_download", return_value=frame) as download:
                payload = service.get("AAPL", interval="4h", range_name="1d")

            download.assert_called_once_with(
                ["AAPL", "SPY"], period="1mo", interval="1h"
            )
            self.assertEqual(len(payload["points"]), 2)
            first = payload["points"][0]
            self.assertEqual(first["open"], 99.0)
            self.assertEqual(first["high"], 105.0)
            self.assertEqual(first["low"], 98.0)
            self.assertEqual(first["close"], 103.0)
            self.assertEqual(first["volume"], 4006.0)
            self.assertEqual(first["interval"], "4h")

    @patch("web_dashboard.chart_series_service.get")
    def test_endpoint_forwards_query_contract(self, get_chart):
        get_chart.return_value = {
            "ticker": "NVDA", "interval": "15m", "range": "5d",
            "points": [], "benchmark": [], "as_of": None,
            "source": "cache", "status": "fresh", "revision": "abc123",
        }

        response = api_native_chart(
            "nvda", refresh=True, interval="15m", range="5d"
        )
        payload = json.loads(response.body)

        get_chart.assert_called_once_with(
            "nvda", interval="15m", range_name="5d", force=True
        )
        self.assertEqual(payload["range"], "5d")

    def test_endpoint_defaults_and_maps_validation_errors(self):
        with patch("web_dashboard.chart_series_service.get", return_value={"ok": True}) as get_chart:
            api_native_chart("nvda")
        get_chart.assert_called_once_with(
            "nvda", interval="1d", range_name="1y", force=False
        )

        with self.assertRaises(HTTPException) as caught:
            api_native_chart("../AAPL")
        self.assertEqual(caught.exception.status_code, 400)

        with self.assertRaises(HTTPException) as caught:
            api_native_chart("AAPL", interval="1m", range="1mo")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertIn("Yahoo no admite", caught.exception.detail)


if __name__ == "__main__":
    unittest.main()
