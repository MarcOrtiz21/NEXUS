import tempfile
import unittest
from datetime import date
from pathlib import Path

from gold_revisions import fetch_gold_revision_diagnostics, revision_diagnostics


class GoldRevisionTests(unittest.TestCase):
    def test_diagnostic_does_not_leak_a_future_revision(self):
        rows = [
            {"period": "2024-01-01", "release_at": "2024-02-13", "value": 100.0},
            {"period": "2024-01-01", "release_at": "2024-03-12", "value": 101.0},
            {"period": "2024-01-01", "release_at": "2024-04-12", "value": 200.0},
        ]
        diagnostic = revision_diagnostics(rows, date(2024, 3, 20))[0]
        self.assertEqual(diagnostic["delta"], 1.0)
        self.assertEqual(diagnostic["revision_count"], 1)
        self.assertEqual(diagnostic["known_release_at"], "2024-03-12")

    def test_source_failure_keeps_diagnostic_as_stale_without_touching_score(self):
        rows = [{"period": "2024-01-01", "release_at": "2024-02-13", "value": 100.0}]
        def unavailable(*args, **kwargs):
            raise RuntimeError("offline")
        with tempfile.TemporaryDirectory() as folder:
            first = fetch_gold_revision_diagnostics(as_of=date(2024, 3, 20), cache_dir=Path(folder), fetcher=lambda *a, **k: rows)
            stale = fetch_gold_revision_diagnostics(as_of=date(2024, 3, 20), refresh=True, cache_dir=Path(folder), fetcher=unavailable)
        self.assertEqual(first["status"], "OK")
        self.assertEqual(stale["series"][0]["status"], "STALE")
        self.assertFalse(stale["score_enabled"])

