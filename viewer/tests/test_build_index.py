"""Unit + end-to-end tests for viewer/build_index.py.

Run with zero extra deps:  python3 -m unittest discover -s viewer/tests
(requires pyyaml, which the toolkit already depends on)
"""
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1]  # viewer/tests -> viewer/

# import build_index.py as a module (its top-level only computes paths from env)
_spec = importlib.util.spec_from_file_location("build_index", VIEWER / "build_index.py")
bi = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bi)


class TestPureHelpers(unittest.TestCase):
    def test_split_frontmatter_present(self):
        fm, body = bi.split_frontmatter("---\nbug_id: 5\nstatus: investigated\n---\n# Title\n\nhi")
        self.assertEqual(fm["bug_id"], 5)
        self.assertTrue(body.startswith("# Title"))

    def test_split_frontmatter_absent(self):
        fm, body = bi.split_frontmatter("# Just a heading\n\ntext")
        self.assertIsNone(fm)
        self.assertTrue(body.startswith("# Just a heading"))

    def test_split_frontmatter_malformed_yaml_is_tolerated(self):
        fm, body = bi.split_frontmatter("---\n: : : not yaml : :\n---\nbody")
        self.assertEqual(fm, {})          # tolerated -> empty dict, not a crash
        self.assertEqual(body, "body")

    def test_clean_md_preserves_identifier_underscores(self):
        # the bug we fixed: '_' must NOT be stripped (blocking_policy stays intact)
        self.assertEqual(bi.clean_md("media.autoplay.blocking_policy"), "media.autoplay.blocking_policy")
        self.assertEqual(bi.clean_md("sPOLICY_STICKY_ACTIVATION"), "sPOLICY_STICKY_ACTIVATION")

    def test_clean_md_strips_bold_code_and_links(self):
        self.assertEqual(bi.clean_md("**bold** and `code`"), "bold and code")
        self.assertEqual(bi.clean_md("see [the spec](https://x.y/z) here"), "see the spec here")

    def test_card_label_strips_bug_prefix_and_investigation(self):
        self.assertEqual(bi.card_label("Bug 123456 Investigation"), "")
        self.assertEqual(bi.card_label("Bug 1870722 — WMF ClearKey EME Playback"), "WMF ClearKey EME Playback")
        self.assertEqual(bi.card_label("Bug 1 Investigation (triage mode)"), "")
        self.assertEqual(bi.card_label("Investigation: Foo Bar"), "Foo Bar")

    def test_preview_priority(self):
        # 1) authored summary wins
        self.assertEqual(bi.preview({"summary": "short headline"}, "# Bug 9 Investigation", "rc text", "9"),
                         "short headline")
        # 2) cleaned heading next
        self.assertEqual(bi.preview({}, "Bug 9 — Real Title", "rc text", "9"), "Real Title")
        # 3) root_cause when heading is noise
        self.assertEqual(bi.preview({}, "Bug 9 Investigation", "the real cause", "9"), "the real cause")
        # 4) bug number as last resort
        self.assertEqual(bi.preview({}, "Bug 9 Investigation", None, "9"), "Bug 9")
        # slug last resort prettifies
        self.assertEqual(bi.preview({}, "", None, "mf-cdm-thing"), "mf cdm thing")

    def test_preview_caps_length(self):
        long = "x" * 400
        out = bi.preview({"summary": long}, "h", None, "1")
        self.assertLessEqual(len(out), 220)
        self.assertTrue(out.endswith("…"))

    def test_as_list(self):
        self.assertEqual(bi.as_list(None), [])
        self.assertEqual(bi.as_list("a"), ["a"])
        self.assertEqual(bi.as_list(["a", "", None, "b"]), ["a", "b"])


class TestEndToEndBuild(unittest.TestCase):
    def _build(self, root: Path) -> list:
        out = root / "out.json"
        env = dict(os.environ, FX_BUG_INVESTIGATION_DIR=str(root), FX_VIEWER_INDEX_OUT=str(out))
        r = subprocess.run([sys.executable, str(VIEWER / "build_index.py")],
                           env=env, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(out.read_text(encoding="utf-8"))

    def test_recursive_scan_numbers_slugs_folders_and_exclusions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "sub").mkdir()
            (root / ".git").mkdir()
            # numeric, with frontmatter (summary + root_cause)
            (root / "bug-111111-investigation.md").write_text(textwrap.dedent("""\
                ---
                bug_id: 111111
                summary: Numbered one headline
                root_cause: the numbered root cause
                depth: deep
                complexity: high
                affected_files:
                  - dom/media/Foo.cpp#L10
                related_bugs: [222, 333]
                investigated_at: 2020-01-01T00:00:00Z
                ---
                # Bug 111111 Investigation
                body text
            """))
            # slug, no frontmatter, "Investigation:" heading
            (root / "bug-mfcdm-thing-investigation.md").write_text(
                "# Investigation: MFCDM Thing\n\nslug body\n")
            # subfolder, number in filename only
            (root / "sub" / "bug-222222-part2-x.md").write_text("# Part 2 — X\n\nsub body\n")
            # excluded scaffolding + hidden dir
            (root / "README.md").write_text("# Readme\n")
            (root / "index.md").write_text("# Index\n")
            (root / ".git" / "bug-999999-x.md").write_text("# nope\n")

            items = self._build(root)
            by_id = {str(i["bug_id"]): i for i in items}

            # 3 included; README/index/.git excluded
            self.assertEqual(len(items), 3)
            self.assertIn("111111", by_id)
            self.assertIn("mfcdm-thing", by_id)        # slug id
            self.assertIn("222222", by_id)

            num = by_id["111111"]
            self.assertEqual(num["summary"], "Numbered one headline")
            self.assertEqual(num["bug_url"], "https://bugzilla.mozilla.org/show_bug.cgi?id=111111")
            self.assertEqual(num["folder"], None)
            self.assertEqual(num["depth"], "deep")
            self.assertEqual(num["related_bugs"], [222, 333])
            self.assertTrue(num["has_frontmatter"])

            slug = by_id["mfcdm-thing"]
            self.assertIsNone(slug["bug_url"])          # no number -> no bugzilla link
            self.assertEqual(slug["summary"], "MFCDM Thing")
            self.assertFalse(slug["has_frontmatter"])

            sub = by_id["222222"]
            self.assertEqual(sub["folder"], "sub")
            self.assertEqual(sub["bug_url"], "https://bugzilla.mozilla.org/show_bug.cgi?id=222222")

    def test_sorted_newest_first(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bug-100001-investigation.md").write_text(
                "---\nbug_id: 100001\ninvestigated_at: 2019-01-01T00:00:00Z\n---\n# old\n")
            (root / "bug-100002-investigation.md").write_text(
                "---\nbug_id: 100002\ninvestigated_at: 2026-01-01T00:00:00Z\n---\n# new\n")
            items = self._build(root)
            self.assertEqual([i["bug_id"] for i in items], [100002, 100001])


if __name__ == "__main__":
    unittest.main()
