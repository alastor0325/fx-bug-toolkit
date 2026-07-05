"""Unit + mock-backend tests for the v3 dashboard collector (base + enrichment).

No network, no real bugzilla-cli, no real API keys or real emails: the Bugzilla
seam (`subprocess.run`) and the Phabricator seam (`conduit`) are stubbed with
canned payloads. Also asserts secrets never reach output.

    python3 -m unittest discover -s dashboard/tests
"""
import json
import os
import re
import subprocess
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

DASH = Path(__file__).resolve().parents[1]  # dashboard/tests -> dashboard/
sys.path.insert(0, str(DASH))
import collect  # noqa: E402

NOW = datetime(2026, 7, 3, 15, 0, 0, tzinfo=timezone.utc)


def bug(**kw):
    base = {"id": 100, "summary": "A bug", "component": "Audio/Video: Playback",
            "severity": "S2", "priority": "P2", "keywords": [],
            "last_change_time": "2026-06-30T00:00:00Z", "flags": []}
    base.update(kw)
    return base


def ni_flag(requestee="you@example.com", setter="asker@example.com",
            status="?", created="2026-06-26T00:00:00Z"):
    return {"name": "needinfo", "status": status, "requestee": requestee,
            "setter": setter, "creation_date": created}


def rev(rid, status="needs-review", bugid=None, author="PHID-A",
        modified="2026-07-01T00:00:00Z", title="A patch", reviewers=None):
    epoch = int(datetime.fromisoformat(modified.replace("Z", "+00:00")).timestamp())
    fields = {"title": title, "authorPHID": author, "dateModified": epoch,
              "status": {"value": status}}
    if bugid is not None:
        fields["bugzilla.bug-id"] = str(bugid)
    r = {"id": rid, "fields": fields}
    if reviewers is not None:
        r["attachments"] = {"reviewers": {"reviewers":
            [{"reviewerPHID": p, "status": "added"} for p in reviewers]}}
    return r


class TestTags(unittest.TestCase):
    def test_derive_tags_core_set(self):
        tags = collect.derive_tags(bug(component="Web Audio", severity="S1",
                                       keywords=["regression", "sec-high"]))
        kinds = {(t["kind"], t["text"]) for t in tags}
        self.assertIn(("component", "Web Audio"), kinds)
        self.assertIn(("severity", "S1"), kinds)
        self.assertIn(("security", "sec"), kinds)
        self.assertIn(("regression", "regression"), kinds)

    def test_derive_tags_omits_absent(self):
        tags = collect.derive_tags(bug(component="", severity="--", keywords=[]))
        self.assertEqual(tags, [])  # nothing derivable → no tags

    def test_is_security_group_or_keyword(self):
        self.assertTrue(collect.is_security(bug(groups=["core-security-release"])))
        self.assertTrue(collect.is_security(bug(keywords=["sec-low"])))
        self.assertFalse(collect.is_security(bug(keywords=["perf"], groups=[])))


class TestBaseItems(unittest.TestCase):
    def test_ni_base_item(self):
        it = collect.ni_base_item(
            bug(id=555, summary="why?", flags=[ni_flag(created="2026-06-26T15:00:00Z")]),
            "you@example.com", NOW)
        self.assertEqual(it["type"], "ni")
        self.assertEqual(it["id"], "555")
        self.assertEqual(it["waiting_days"], 7)          # from the flag's set date
        self.assertEqual(it["from"], "asker@example.com")
        self.assertIsNone(it["brief"])
        self.assertIsNone(it["solvable"])
        self.assertTrue(any(t["kind"] == "component" for t in it["tags"]))

    def test_ni_base_item_picks_my_flag(self):
        it = collect.ni_base_item(
            bug(flags=[ni_flag(requestee="other@example.com", setter="x@example.com"),
                       ni_flag(requestee="you@example.com", setter="mine@example.com")]),
            "you@example.com", NOW)
        self.assertEqual(it["from"], "mine@example.com")

    def test_review_base_item_group_only(self):
        it = collect.review_base_item(
            rev(3210, author="PHID-A", modified="2026-06-30T15:00:00Z", title="Fix seek",
                reviewers=["PHID-GRP", "PHID-OTHER"]),
            {"PHID-A": "contributor", "PHID-GRP": "#media-playback-reviewers"},
            NOW, {"PHID-GRP"}, my_phid="PHID-ME")
        self.assertEqual(it["id"], "D3210")
        self.assertEqual(it["author"], "contributor")
        self.assertEqual(it["waiting_days"], 3)
        self.assertEqual(it["reviewers"], ["#media-playback-reviewers"])  # only my group, not PHID-OTHER
        self.assertFalse(it["direct"])                                    # I'm not a reviewer personally
        self.assertIsNone(it["brief"])

    def test_review_base_item_direct(self):
        it = collect.review_base_item(
            rev(1, reviewers=["PHID-ME", "PHID-GRP"]),
            {"PHID-ME": "you", "PHID-GRP": "#grp"}, NOW, {"PHID-ME", "PHID-GRP"}, my_phid="PHID-ME")
        self.assertTrue(it["direct"])
        self.assertEqual(it["reviewers"], ["you", "#grp"])

    def test_review_requires_matches_me_or_my_groups(self):
        r = rev(9, reviewers=["PHID-ME", "PHID-GRP", "PHID-STRANGER"])
        names = {"PHID-ME": "you", "PHID-GRP": "#media-playback-reviewers"}
        self.assertEqual(collect.review_requires(r, {"PHID-ME", "PHID-GRP"}, names),
                         ["you", "#media-playback-reviewers"])
        self.assertEqual(collect.review_requires(r, set(), names), [])   # nothing mine
        self.assertEqual(collect.review_requires(rev(9), {"PHID-ME"}, names), [])  # no reviewers attachment


class TestPatchStatus(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(collect.patch_status(rev(1, "needs-review")), "in-review")
        self.assertEqual(collect.patch_status(rev(1, "needs-revision")), "needs-revision")
        self.assertEqual(collect.patch_status(rev(1, "accepted")), "accepted")
        self.assertEqual(collect.patch_status(rev(1, "draft")), "wip")
        self.assertEqual(collect.patch_status(rev(1, "published")), "landed")

    def test_best_patch_status_prefers_needs_revision(self):
        revs = [rev(1, "accepted"), rev(2, "needs-revision"), rev(3, "needs-review")]
        self.assertEqual(collect.best_patch_status(revs), "needs-revision")


class TestMyBugs(unittest.TestCase):
    def test_union_assigned_and_revision_only(self):
        assigned = [bug(id=10, summary="assigned one")]
        my_revs = [rev(1, "needs-revision", bugid=10),      # patch on an assigned bug
                   rev(2, "accepted", bugid=99, title="Bug 99 - rev only")]  # revision-only bug
        items = collect.build_my_bugs(assigned, my_revs, NOW)
        by_id = {i["id"]: i for i in items}
        self.assertEqual(set(by_id), {"10", "99"})               # union
        self.assertEqual(by_id["10"]["patch_status"], "needs-revision")
        self.assertTrue(by_id["10"]["tags"])                     # assigned bug has field tags
        self.assertEqual(by_id["99"]["patch_status"], "accepted")
        self.assertEqual(by_id["99"]["tags"], [])                # revision-only: limited info

    def test_assigned_without_patch(self):
        items = collect.build_my_bugs([bug(id=5)], [], NOW)
        self.assertEqual(items[0]["patch_status"], "none")


class TestBuildBaseAndEnrichment(unittest.TestCase):
    def test_build_base_shape(self):
        base = collect.build_base(
            "you@example.com",
            needinfos=[bug(id=1, flags=[ni_flag()])],
            reviews=[rev(9, "needs-review", author="PHID-A")],
            review_names={"PHID-A": "alice"},
            assigned=[bug(id=2)],
            my_revisions=[rev(3, "accepted", bugid=2)],
            now=NOW)
        self.assertEqual(base["status"], "running")
        self.assertIsNone(base["generated_at"])
        self.assertEqual(base["user"], "you@example.com")
        s = base["sections"]
        self.assertEqual(len(s["needinfos"]), 1)
        self.assertEqual(len(s["reviews"]), 1)
        self.assertEqual(s["my_bugs"][0]["patch_status"], "accepted")

    def test_build_base_drops_self_authored_reviews(self):
        base = collect.build_base(
            "you@example.com", [],
            reviews=[rev(1, author="PHID-ME", reviewers=["PHID-GRP"]),      # my own patch → excluded
                     rev(2, author="PHID-OTHER", reviewers=["PHID-GRP"])],  # someone else's → kept
            review_names={}, assigned=[], my_revisions=[], now=NOW,
            review_mine_phids={"PHID-GRP"}, review_my_phid="PHID-ME")
        self.assertEqual([r["id"] for r in base["sections"]["reviews"]], ["D2"])

    def test_apply_enrichment_merges_and_readies(self):
        base = collect.build_base("you@example.com", [bug(id=1, flags=[ni_flag()])],
                                  [], {}, [], [], NOW)
        enriched = collect.apply_enrichment(base, {
            "1": {"brief": {"bug": "b", "ask": "a"}, "solvable": True,
                  "solvable_reason": "clear STR", "extra_tags": [{"text": "ready", "kind": "good"}]},
        }, NOW)
        item = enriched["sections"]["needinfos"][0]
        self.assertEqual(item["brief"], {"bug": "b", "ask": "a"})
        self.assertTrue(item["solvable"])
        self.assertEqual(item["solvable_reason"], "clear STR")
        self.assertTrue(any(t["text"] == "ready" for t in item["tags"]))
        self.assertEqual(enriched["status"], "ready")
        self.assertTrue(enriched["generated_at"].endswith("Z"))

    def test_apply_enrichment_ignores_unknown_ids(self):
        base = collect.build_base("you@example.com", [], [], {}, [], [], NOW)
        out = collect.apply_enrichment(base, {"nope": {"brief": {"x": 1}}}, NOW)
        self.assertEqual(out["status"], "ready")   # no crash on unmatched id

    def test_status_payload(self):
        base = collect.build_base("you@example.com", [bug(id=1, flags=[ni_flag()])],
                                  [], {}, [bug(id=2)], [], NOW)
        p = collect.status_payload(base, "running")
        self.assertEqual(p["state"], "running")
        self.assertEqual(p["counts"]["needinfos"], 1)
        self.assertEqual(p["counts"]["my_bugs"], 1)


class TestConduitForm(unittest.TestCase):
    def test_flatten_nested(self):
        form = collect.conduit_form({"constraints": {"reviewerPHIDs": ["A", "B"]},
                                     "api.token": "tok"})
        self.assertEqual(form["constraints[reviewerPHIDs][0]"], "A")
        self.assertEqual(form["constraints[reviewerPHIDs][1]"], "B")
        self.assertEqual(form["api.token"], "tok")


class TestBackendSeams(unittest.TestCase):
    def test_run_bugzilla_cli_parses_and_raises(self):
        orig = collect.subprocess.run
        collect.subprocess.run = lambda *a, **k: types.SimpleNamespace(
            returncode=0, stdout='[{"id":1}]', stderr="")
        try:
            self.assertEqual(collect.run_bugzilla_cli(["needinfos", "--user", "me@example.com"])[0]["id"], 1)
        finally:
            collect.subprocess.run = orig
        collect.subprocess.run = lambda *a, **k: types.SimpleNamespace(returncode=1, stdout="", stderr="boom")
        try:
            with self.assertRaises(RuntimeError):
                collect.run_bugzilla_cli(["assigned", "--user", "me@example.com"])
        finally:
            collect.subprocess.run = orig

    def test_fetch_phabricator_includes_group_reviews(self):
        def fake_conduit(method, params, token):
            if method == "user.whoami":
                return {"phid": "PHID-ME", "userName": "me"}
            if method == "project.search":                       # my review groups
                return {"data": [{"phid": "PHID-GRP", "fields": {"slug": "media-playback-reviewers"}}]}
            if method == "differential.revision.search":
                if "authorPHIDs" in params["constraints"]:
                    return {"data": [rev(5, "accepted", bugid=2)]}
                # the reviewer constraint should include my group's PHID
                assert "PHID-GRP" in params["constraints"]["reviewerPHIDs"]
                return {"data": [rev(9, "needs-review", author="PHID-A", reviewers=["PHID-GRP"])]}
            if method == "user.search":
                return {"data": [{"phid": "PHID-A", "fields": {"username": "alice"}}]}
            return {}

        orig = collect.conduit
        collect.conduit = fake_conduit
        try:
            reviews, names, my_revs, mine, my_phid = collect.fetch_phabricator("api-fake")
            self.assertEqual(reviews[0]["id"], 9)
            self.assertEqual(names["PHID-A"], "alice")
            self.assertEqual(names["PHID-GRP"], "#media-playback-reviewers")
            self.assertIn("PHID-GRP", mine)
            self.assertEqual(my_phid, "PHID-ME")
            self.assertEqual(my_revs[0]["id"], 5)
            # the review carries which group it's requested on, and is not "direct"
            it = collect.review_base_item(reviews[0], names, NOW, mine, my_phid)
            self.assertEqual(it["reviewers"], ["#media-playback-reviewers"])
            self.assertFalse(it["direct"])
        finally:
            collect.conduit = orig

    def test_fetch_phabricator_degrades_on_error(self):
        orig = collect.conduit
        collect.conduit = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down"))
        try:
            self.assertEqual(collect.fetch_phabricator("api-fake"), ([], {}, [], set(), None))
        finally:
            collect.conduit = orig


class TestResolveUser(unittest.TestCase):
    def test_explicit_env_wins(self):
        os.environ["FX_DASHBOARD_USER"] = "you@example.com"
        try:
            self.assertEqual(collect.resolve_user_email(
                whoami_run=lambda: (_ for _ in ()).throw(AssertionError("whoami called"))),
                "you@example.com")
        finally:
            os.environ.pop("FX_DASHBOARD_USER", None)

    def test_falls_back_to_whoami(self):
        os.environ.pop("FX_DASHBOARD_USER", None)
        fake = types.SimpleNamespace(returncode=0, stdout="Dev User <you@example.com>", stderr="")
        self.assertEqual(collect.resolve_user_email(whoami_run=lambda: fake), "you@example.com")


class TestSecretHygiene(unittest.TestCase):
    def test_secrets_never_reach_output(self):
        os.environ["FX_PHABRICATOR_TOKEN"] = "api-SECRET-should-not-leak"
        os.environ["BUGZILLA_API_KEY"] = "BMOKEY-should-not-leak"
        try:
            base = collect.build_base("you@example.com", [bug(id=1, flags=[ni_flag()])],
                                      [], {}, [], [], NOW)
            data = collect.apply_enrichment(base, {}, NOW)
            blob = json.dumps(data) + json.dumps(collect.status_payload(data, "ready"))
            self.assertNotIn("SECRET-should-not-leak", blob)
            self.assertNotIn("BMOKEY-should-not-leak", blob)
        finally:
            os.environ.pop("FX_PHABRICATOR_TOKEN", None)
            os.environ.pop("BUGZILLA_API_KEY", None)

    def test_source_has_no_hardcoded_key(self):
        src = (DASH / "collect.py").read_text(encoding="utf-8")
        self.assertIsNone(re.search(r"api-[a-z0-9]{20,}", src),
                          "a Conduit-token-shaped literal is hardcoded in collect.py")


if __name__ == "__main__":
    unittest.main()
