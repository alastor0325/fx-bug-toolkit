"""Unit tests for skills/triage/bmo_query.py (pure functions only; no network)."""

import importlib.util
import unittest
import urllib.parse
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "skills" / "triage" / "bmo_query.py"
_spec = importlib.util.spec_from_file_location("bmo_query", _PATH)
bq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bq)


class TestParseComponent(unittest.TestCase):
    def test_qualified(self):
        self.assertEqual(bq.parse_component("Core::DOM: Events"), ("Core", "DOM: Events"))

    def test_qualified_keeps_later_colons(self):
        self.assertEqual(bq.parse_component("Core::Spelling Checker: en-US Dictionary"),
                         ("Core", "Spelling Checker: en-US Dictionary"))

    def test_bare_uses_default_product(self):
        self.assertEqual(bq.parse_component("XSLT", "Core"), ("Core", "XSLT"))

    def test_bare_without_product_raises(self):
        with self.assertRaises(ValueError):
            bq.parse_component("XSLT")


class TestUntriagedQuery(unittest.TestCase):
    def test_filters_match_bugbot(self):
        p = dict(bq.untriaged_query([("Core", "XML")]))
        self.assertEqual(p["resolution"], "---")
        self.assertEqual(p["v1"], "defect")
        self.assertEqual((p["o2"], p["v2"]), ("notsubstring", "needinfo?"))
        self.assertEqual(p["v3"], "--, n/a")
        self.assertEqual(p["v4"], "[no-nag]")
        self.assertEqual((p["o5"], p["v5"]), ("nowords", "meta"))
        self.assertEqual(p["keywords"], "intermittent-failure")
        self.assertEqual(p["email2"], "wptsync@mozilla.bugs")

    def test_pairs_are_product_scoped_and_balanced(self):
        params = bq.untriaged_query([("Core", "Session Restore"), ("Core", "XML")])
        d = dict(params)
        self.assertEqual(d["j6"], "OR")
        self.assertEqual((d["v8"], d["v9"]), ("Core", "Session Restore"))
        self.assertEqual((d["v12"], d["v13"]), ("Core", "XML"))
        ops = [v for k, v in params if k.startswith("f") and v in ("OP", "CP")]
        self.assertEqual(ops.count("OP"), ops.count("CP"))
        self.assertEqual(ops[-1], "CP")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            bq.untriaged_query([])


class TestBuglistParams(unittest.TestCase):
    def test_keeps_query_drops_paging_and_fields(self):
        url = ("https://bugzilla.mozilla.org/buglist.cgi?resolution=---&f1=bug_type&o1=equals"
               "&v1=defect&limit=20&list_id=123&include_fields=id&order=bug_id")
        self.assertEqual(bq.buglist_params(url),
                         [("resolution", "---"), ("f1", "bug_type"), ("o1", "equals"), ("v1", "defect")])

    def test_rest_url_accepted(self):
        self.assertEqual(bq.buglist_params("https://bugzilla.mozilla.org/rest/bug?id=1,2"), [("id", "1,2")])

    def test_rejects_other_hosts_paths_and_empty(self):
        for url in ("https://example.com/buglist.cgi?id=1",
                    "http://bugzilla.mozilla.org/buglist.cgi?id=1",
                    "https://bugzilla.mozilla.org/show_bug.cgi?id=1",
                    "https://bugzilla.mozilla.org/buglist.cgi?limit=5"):
            with self.assertRaises(ValueError, msg=url):
                bq.buglist_params(url)


class TestRestUrlAndOrder(unittest.TestCase):
    def test_rest_url_adds_fields(self):
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(bq.rest_url([("id", "1")])).query)
        self.assertEqual(q["id"], ["1"])
        self.assertIn("component", q["include_fields"][0])

    def test_oldest_first(self):
        bugs = [{"id": 3, "creation_time": "2026-02-01"}, {"id": 2, "creation_time": "2026-01-01"},
                {"id": 1, "creation_time": "2026-02-01"}]
        self.assertEqual([b["id"] for b in bq.oldest_first(bugs)], [2, 1, 3])


if __name__ == "__main__":
    unittest.main()
