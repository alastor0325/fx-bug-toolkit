"""Unit tests for the dashboard storage layer (paths, atomic IO, assemble/overlay).

    python3 -m unittest discover -s dashboard/tests
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

DASH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DASH))
import store  # noqa: E402


class StoreCase(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("FX_DASHBOARD_DIR")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["FX_DASHBOARD_DIR"] = self.tmp.name

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("FX_DASHBOARD_DIR", None)
        else:
            os.environ["FX_DASHBOARD_DIR"] = self._prev
        self.tmp.cleanup()


class TestPathsAndIO(StoreCase):
    def test_data_dir_env_override_else_default(self):
        self.assertEqual(store.data_dir(), Path(self.tmp.name))
        del os.environ["FX_DASHBOARD_DIR"]
        self.assertEqual(store.data_dir(), Path.home() / ".fx-bug-toolkit" / "dashboard")

    def test_atomic_write_then_read_roundtrip(self):
        p = store.data_dir() / "x.json"
        store.atomic_write_json(p, {"a": 1})
        self.assertEqual(store.read_json(p), {"a": 1})
        # no leftover temp files beside it
        self.assertEqual([f for f in os.listdir(self.tmp.name) if f.startswith(".tmp-")], [])

    def test_read_json_missing_or_corrupt_returns_default(self):
        self.assertEqual(store.read_json(store.data_dir() / "nope.json", []), [])
        bad = store.data_dir() / "bad.json"; bad.write_text("{not json")
        self.assertEqual(store.read_json(bad, {"d": 1}), {"d": 1})

    def test_generated_flips_with_manifest(self):
        self.assertFalse(store.generated())
        store.atomic_write_json(store.manifest_path(), {"user": "you@example.com"})
        self.assertTrue(store.generated())


class TestSectionsAndOverlay(StoreCase):
    def test_section_roundtrip_and_default(self):
        self.assertEqual(store.read_section("reviews")["status"], "missing")
        store.write_section("reviews", [{"id": "5"}], "ready", "2026-07-05T00:00:00Z")
        s = store.read_section("reviews")
        self.assertEqual((s["status"], s["items"]), ("ready", [{"id": "5"}]))

    def test_overlay_roundtrip(self):
        self.assertEqual(store.read_overlay(), [])
        store.write_overlay([{"id": "7", "added": True}])
        self.assertEqual(store.read_overlay(), [{"id": "7", "added": True}])

    def test_merge_overlay_dedups_collected_wins_keeps_pin(self):
        collected = [{"id": "1", "title": "real"}]
        overlay = [{"id": "1", "title": "stale"}, {"id": "9", "title": "pinned"}]
        out = store.merge_overlay(collected, overlay)
        by_id = {i["id"]: i for i in out}
        self.assertEqual(by_id["1"]["title"], "real")     # collected wins
        self.assertTrue(by_id["1"]["added"])              # but keeps the pin marker
        self.assertTrue(by_id["9"]["added"])              # user-only appended


class TestAssemble(StoreCase):
    def _seed(self, ni_status="ready", rev_status="ready"):
        store.atomic_write_json(store.manifest_path(),
                                {"user": "you@example.com", "generated_at": "2026-07-05T00:00:00Z"})
        store.write_section("needinfos", [{"id": "a"}], ni_status, "2026-07-05T00:00:00Z")
        store.write_section("reviews", [{"id": "b"}], rev_status, "2026-07-05T00:00:00Z")
        store.write_section("my_bugs", [{"id": "c"}], "ready", "2026-07-05T00:00:00Z")

    def test_assemble_merges_sections_status_and_overlay(self):
        self._seed()
        store.write_overlay([{"id": "z", "title": "pinned"}])
        data = store.assemble()
        self.assertEqual(set(data["sections"]), {"needinfos", "reviews", "my_bugs"})
        self.assertEqual(data["user"], "you@example.com")
        self.assertEqual(data["status"], "ready")
        self.assertEqual([b["id"] for b in data["sections"]["my_bugs"]], ["c", "z"])   # overlay merged
        self.assertTrue(data["sections"]["my_bugs"][1]["added"])

    def test_assemble_overall_running_if_any_section_running(self):
        self._seed(rev_status="running")
        data = store.assemble()
        self.assertEqual(data["status"], "running")
        self.assertEqual(data["section_status"]["reviews"], "running")
        self.assertEqual(data["section_status"]["needinfos"], "ready")

    def test_status_payload_counts(self):
        self._seed()
        p = store.status_payload()
        self.assertEqual(p["state"], "ready")
        self.assertEqual(p["counts"], {"needinfos": 1, "reviews": 1, "my_bugs": 1})


if __name__ == "__main__":
    unittest.main()
