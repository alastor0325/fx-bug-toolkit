"""Tests for the dashboard drain's deterministic half (queue/results merge).

Pure helpers + an end-to-end `apply` against temp queue/results files (no Claude,
no network).

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
import drain  # noqa: E402


class TestPureHelpers(unittest.TestCase):
    def test_action_key(self):
        self.assertEqual(drain.action_key("111", "draft-reply"), "111::draft-reply")

    def test_pending_excludes_done(self):
        q = [{"id": "1", "action": "a", "status": "queued"},
             {"id": "2", "action": "b", "status": "done"}]
        self.assertEqual([e["id"] for e in drain.pending(q)], ["1"])

    def test_merge_results_later_wins_keeps_others(self):
        merged = drain.merge_results({"a": {"summary": "old"}, "b": {"summary": "keep"}},
                                     {"a": {"summary": "new"}})
        self.assertEqual(merged["a"]["summary"], "new")
        self.assertEqual(merged["b"]["summary"], "keep")

    def test_mark_done_flips_matching(self):
        q = [{"id": "1", "action": "draft-reply", "status": "queued"},
             {"id": "1", "action": "review", "status": "queued"}]
        out = drain.mark_done(q, {"1::draft-reply"})
        self.assertEqual(out[0]["status"], "done")
        self.assertEqual(out[1]["status"], "queued")   # untouched

    def test_drop_done_prunes_processed(self):
        q = [{"id": "1", "action": "a", "status": "done"},
             {"id": "2", "action": "b", "status": "queued"}]
        self.assertEqual([e["id"] for e in drain.drop_done(q)], ["2"])


class TestApplyEndToEnd(unittest.TestCase):
    def test_apply_merges_and_marks_done(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            qf = root / "queue.json"
            rf = root / "results.json"
            qf.write_text(json.dumps([
                {"id": "111", "action": "draft-reply", "status": "queued"},
                {"id": "D9", "action": "review", "status": "queued"},
            ]))
            new = root / "new.json"
            new.write_text(json.dumps({"111::draft-reply": {"summary": "drafted"}}))

            # point drain at the temp files
            drain.QUEUE = qf
            drain.RESULTS = rf
            try:
                rc = drain.cmd_apply(str(new))
                self.assertEqual(rc, 0)
                results = json.loads(rf.read_text())
                self.assertEqual(results["111::draft-reply"]["summary"], "drafted")
                queue = json.loads(qf.read_text())
                keys = {drain.action_key(e["id"], e["action"]) for e in queue}
                # processed entry is pruned; the untouched one stays pending
                self.assertNotIn("111::draft-reply", keys)
                self.assertIn("D9::review", keys)
            finally:
                drain.QUEUE = DASH / "queue.json"
                drain.RESULTS = DASH / "results.json"

    def test_apply_rejects_non_object(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad.json"
            bad.write_text("[1,2,3]")
            self.assertEqual(drain.cmd_apply(str(bad)), 1)


if __name__ == "__main__":
    unittest.main()
