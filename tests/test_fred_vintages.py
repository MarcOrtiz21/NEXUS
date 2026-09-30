import tempfile
import unittest
from datetime import date
from pathlib import Path

from fred_vintages import fetch_initial_releases, fetch_revision_history, first_release_rows, known_rows, lagged_change, parse_initial_releases


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FredVintageTests(unittest.TestCase):
    def test_revision_uses_one_value_per_period_and_excludes_future(self):
        rows = [
            {"period": "2024-01-01", "release_at": "2024-02-13", "value": 100.0},
            {"period": "2024-01-01", "release_at": "2024-03-12", "value": 101.0},
            {"period": "2024-02-01", "release_at": "2024-03-12", "value": 103.0},
            {"period": "2024-01-01", "release_at": "2024-04-12", "value": 999.0},
        ]
        visible = known_rows(rows, "2024-03-20")
        self.assertEqual([row["value"] for row in visible], [101.0, 103.0])
        self.assertAlmostEqual(lagged_change(rows, "2024-03-20", periods=1, percent=True), (103 / 101 - 1) * 100)
        self.assertEqual(first_release_rows(rows)[0]["value"], 100.0)
        rows.append({"period": "2024-02-01", "release_at": "2024-03-15", "value": None})
        self.assertEqual(len(known_rows(rows, "2024-03-20")), 1)

    def test_revision_fetch_paginates_and_preserves_revised_values(self):
        calls = []
        def get(*args, **kwargs):
            params = kwargs["params"]
            calls.append(params)
            return _Response({"count": 2, "observations": [{
                "date": "2024-01-01", "realtime_start": "2024-02-13" if params["offset"] == 0 else "2024-03-12",
                "value": "100" if params["offset"] == 0 else "101",
            }]})
        with tempfile.TemporaryDirectory() as folder:
            rows = fetch_revision_history("TEST", "2024-01-01", "2024-12-31", api_key="x", cache_dir=Path(folder), request_get=get)
            cached = fetch_revision_history("TEST", "2024-01-01", "2024-12-31", api_key="x", cache_dir=Path(folder), request_get=get)
        self.assertEqual(rows, cached)
        self.assertEqual([row["value"] for row in rows], [100.0, 101.0])
        self.assertEqual([item["offset"] for item in calls], [0, 1])
        self.assertEqual(calls[0]["output_type"], 1)

    def test_parser_keeps_release_date_and_drops_bad_values(self):
        rows = parse_initial_releases({"observations": [
            {"date": "2024-01-01", "realtime_start": "2024-02-13", "realtime_end": "2025-01-01", "value": "309.685"},
            {"date": "2024-02-01", "realtime_start": "2024-01-01", "value": "1"},
            {"date": "2024-03-01", "realtime_start": "2024-04-01", "value": "."},
        ]})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["release_at"], "2024-02-13")

    def test_future_release_is_invisible(self):
        rows = [
            {"period": "2024-01-01", "release_at": "2024-02-13", "value": 100.0},
            {"period": "2024-02-01", "release_at": "2024-03-12", "value": 102.0},
        ]
        self.assertEqual(len(known_rows(rows, date(2024, 3, 1))), 1)
        self.assertAlmostEqual(lagged_change(rows, date(2024, 3, 20), periods=1, percent=True), 2.0)

    def test_fetch_uses_cache_without_second_request(self):
        calls = []

        def get(*args, **kwargs):
            calls.append(kwargs["params"])
            return _Response({"observations": [
                {"date": "2024-01-01", "realtime_start": "2024-02-13", "value": "100"},
            ]})

        with tempfile.TemporaryDirectory() as folder:
            first = fetch_initial_releases("TEST", "2024-01-01", "2024-12-31", api_key="x", cache_dir=Path(folder), request_get=get)
            second = fetch_initial_releases("TEST", "2024-01-01", "2024-12-31", api_key="x", cache_dir=Path(folder), request_get=get)
        self.assertEqual(first, second)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["output_type"], 4)


if __name__ == "__main__":
    unittest.main()
