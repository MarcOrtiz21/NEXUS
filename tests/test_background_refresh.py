import tempfile
import unittest
from pathlib import Path
from unittest import mock

import requests

import background_refresh


class _Response:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


class _Session:
    def __init__(self, health=True, refresh_status=200):
        self.health = health
        self.refresh_status = refresh_status
        self.posts = []

    def get(self, url, timeout):
        if not self.health:
            raise requests.ConnectionError("down")
        return _Response()

    def post(self, url, timeout):
        self.posts.append(url)
        return _Response(self.refresh_status, {"captured_at_utc": "2030-01-02T08:00:00+00:00"})


class BackgroundRefreshTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(background_refresh, "LOCK_FILE", Path(self.directory.name) / "x.lock")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.directory.cleanup)

    def test_running_engine_receives_the_refresh(self):
        session = _Session(health=True)
        with mock.patch.object(background_refresh, "refresh_headless") as headless:
            self.assertEqual(background_refresh.run(session), 0)
        self.assertEqual(session.posts, [f"{background_refresh.ENGINE_URL}/api/native/refresh"])
        headless.assert_not_called()

    def test_without_engine_builds_headless(self):
        with mock.patch.object(background_refresh, "refresh_headless", return_value="t") as headless:
            self.assertEqual(background_refresh.run(_Session(health=False)), 0)
        headless.assert_called_once()

    def test_engine_error_reports_failure(self):
        with self.assertLogs(level="ERROR"):
            self.assertEqual(background_refresh.run(_Session(refresh_status=503)), 1)

    def test_concurrent_run_is_skipped(self):
        with background_refresh.single_run() as first:
            self.assertTrue(first)
            with mock.patch.object(background_refresh, "refresh_headless") as headless:
                self.assertEqual(background_refresh.run(_Session(health=False)), 0)
            headless.assert_not_called()


if __name__ == "__main__":
    unittest.main()
