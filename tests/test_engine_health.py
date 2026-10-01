import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from web_dashboard import api_health, code_changed_since_start


class EngineHealthTests(unittest.TestCase):
    def test_health_reports_process_and_code_state(self):
        payload = json.loads(api_health().body)
        self.assertEqual(payload["pid"], os.getpid())
        self.assertIn("code_stale", payload)

    def test_detects_module_modified_after_start(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "risk_filters").mkdir()
            module = root / "risk_filters" / "calendar.py"
            module.write_text("x = 1\n")
            started = time.time() + 5
            self.assertFalse(code_changed_since_start(root, started))
            os.utime(module, (started + 1, started + 1))
            self.assertTrue(code_changed_since_start(root, started))


if __name__ == "__main__":
    unittest.main()
