import unittest
from unittest.mock import patch

from macos_notifications import detect_notification_events, snapshot_state


class MacOSNotificationTests(unittest.TestCase):
    def _snap(self, status, macro, ops, vix):
        return {
            "status": status,
            "decision": {
                "macro_action": macro,
                "operational_action": ops,
                "action": ops,
            },
            "data": {"VIX": vix},
        }

    def test_operational_action_change_notifies(self):
        prev = snapshot_state(self._snap("HEALTHY", "COMPRAR", "COMPRAR", 18.0))
        curr = snapshot_state(self._snap("HEALTHY", "COMPRAR", "ESPERAR", 18.0))
        events = detect_notification_events(prev, curr)
        self.assertTrue(any("Señal operativa" in title for title, _ in events))

    def test_vix_threshold_cross_notifies(self):
        prev = snapshot_state(self._snap("HEALTHY", "ESPERAR", "ESPERAR", 28.0))
        curr = snapshot_state(self._snap("CAUTION", "ESPERAR", "ESPERAR", 31.0))
        events = detect_notification_events(prev, curr)
        self.assertTrue(any("VIX" in title for title, _ in events))

    def test_first_snapshot_does_not_notify(self):
        curr = snapshot_state(self._snap("HEALTHY", "COMPRAR", "COMPRAR", 16.0))
        self.assertEqual(detect_notification_events(None, curr), [])

    @patch("macos_notifications.send_macos_notification", return_value=True)
    @patch("macos_notifications.notifications_enabled", return_value=True)
    def test_notify_snapshot_change_sends_events(self, _enabled, send_mock):
        from macos_notifications import notify_snapshot_change

        previous = self._snap("HEALTHY", "COMPRAR", "COMPRAR", 18.0)
        current = self._snap("BLOCKED", "COMPRAR", "ESPERAR", 18.0)
        sent = notify_snapshot_change(previous, current)
        self.assertGreaterEqual(sent, 1)
        send_mock.assert_called()


if __name__ == "__main__":
    unittest.main()
