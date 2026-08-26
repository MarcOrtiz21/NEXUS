import unittest

from snapshot_service import SnapshotService


class SnapshotServiceTests(unittest.TestCase):
    def test_reuses_fresh_snapshot_and_force_rebuilds(self):
        calls = []

        def builder(*, export=False):
            calls.append(export)
            return {"sequence": len(calls), "export": export}

        service = SnapshotService(builder=builder, ttl_seconds=60)

        first = service.get()
        second = service.get()
        refreshed = service.get(force=True, export=True)

        self.assertIs(first, second)
        self.assertEqual(first["sequence"], 1)
        self.assertEqual(refreshed["sequence"], 2)
        self.assertEqual(calls, [False, True])

    def test_invalidate_marks_snapshot_for_rebuild(self):
        calls = []

        def builder(*, export=False):
            calls.append(True)
            return {"sequence": len(calls)}

        service = SnapshotService(builder=builder, ttl_seconds=60)
        service.get()
        service.invalidate()
        rebuilt = service.get()

        self.assertEqual(rebuilt["sequence"], 2)

    def test_returns_previous_snapshot_when_rebuild_is_busy(self):
        import threading

        started = threading.Event()
        release = threading.Event()
        calls = []

        def builder(*, export=False):
            calls.append(export)
            if len(calls) == 1:
                return {"n": 1}
            started.set()
            release.wait(2)
            return {"n": 2}

        service = SnapshotService(builder=builder, ttl_seconds=0)
        first = service.get()
        worker = threading.Thread(target=lambda: service.get(force=True))
        worker.start()
        self.assertTrue(started.wait(1))
        third = service.get()
        self.assertEqual(third["n"], 1)
        self.assertIs(third, first)
        release.set()
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())


if __name__ == "__main__":
    unittest.main()
