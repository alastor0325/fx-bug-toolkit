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

    def test_rev_stage_needs_review_without_reviewer_is_wip(self):
        # needs-review WITH a reviewer = in review; WITHOUT = wip (not really out
        # for review yet — I still have to request it). Bug 1909543 in the wild.
        self.assertEqual(collect.rev_stage(rev(1, "needs-review", reviewers=["PHID-R"])), "in-review")
        self.assertEqual(collect.rev_stage(rev(1, "needs-review", reviewers=[])), "wip")
        self.assertEqual(collect.rev_stage(rev(1, "needs-review")), "wip")   # no attachment at all
        self.assertEqual(collect.rev_stage(rev(1, "needs-revision", reviewers=[])), "needs-revision")

    def test_aggregate_patch_ready_only_when_all_accepted(self):
        # Bug 2051326 in the wild: Part 2 accepted, Part 1 still needs-review with
        # reviewers → NOT ready to land; it's in-review, 1 of 2 accepted.
        agg = collect.aggregate_patch([rev(1, "accepted", reviewers=["PHID-R"]),
                                       rev(2, "needs-review", reviewers=["PHID-R"])])
        self.assertEqual(agg["status"], "in-review")
        self.assertEqual((agg["accepted"], agg["total"]), (1, 2))
        # every part accepted → r+ land it
        allacc = collect.aggregate_patch([rev(1, "accepted"), rev(2, "accepted")])
        self.assertEqual((allacc["status"], allacc["accepted"], allacc["total"]), ("accepted", 2, 2))

    def test_aggregate_patch_precedence_and_edges(self):
        # a bounced part outranks an accepted one (ball back in my court)
        self.assertEqual(collect.aggregate_patch(
            [rev(1, "accepted"), rev(2, "needs-revision")])["status"], "needs-revision")
        # accepted + no-reviewer part → wip (I must get the second part reviewed)
        self.assertEqual(collect.aggregate_patch(
            [rev(1, "accepted"), rev(2, "needs-review", reviewers=[])])["status"], "wip")
        # landed parts are ignored; empty stack → none
        self.assertEqual(collect.aggregate_patch([rev(1, "published")])["status"], "none")
        self.assertEqual(collect.aggregate_patch([])["status"], "none")
        # primary revision is the one that set the stage (drives reviewer + link)
        agg = collect.aggregate_patch([rev(7, "accepted"), rev(8, "needs-revision")])
        self.assertEqual(agg["primary"]["id"], 8)


class TestMyBugs(unittest.TestCase):
    def test_union_assigned_and_revision_only(self):
        assigned = [bug(id=10, summary="assigned one")]
        my_revs = [rev(1, "needs-revision", bugid=10, reviewers=["PHID-USER-p"]),  # patch on assigned bug
                   rev(2, "accepted", bugid=99, title="Bug 99 - Part 1: rev title")]  # revision-only bug
        details = {"99": {"id": 99, "is_open": True, "summary": "The real bug summary",
                          "severity": "S2", "keywords": ["regression"]}}
        items = collect.build_my_bugs(assigned, my_revs, NOW, {"PHID-USER-p": "padenot"}, details)
        by_id = {i["id"]: i for i in items}
        self.assertEqual(set(by_id), {"10", "99"})               # union
        self.assertEqual(by_id["10"]["patch_status"], "needs-revision")
        self.assertTrue(by_id["10"]["is_open"])                  # collected bugs are open
        self.assertEqual(by_id["10"]["reviewer"], "padenot")     # resolved from names
        self.assertTrue(by_id["10"]["rev_url"].endswith("/D1"))  # patch link
        self.assertIn("last_activity_days", by_id["10"])
        self.assertTrue(by_id["10"]["assigned"])                 # assigned-to-me path
        self.assertFalse(by_id["99"]["assigned"])                # revision-only → not assigned
        self.assertEqual(by_id["99"]["patch_status"], "accepted")
        self.assertEqual(by_id["99"]["title"], "The real bug summary")  # bug summary, NOT the rev title
        self.assertIn({"text": "S2", "kind": "severity"}, by_id["99"]["tags"])  # tags from the real bug

    def test_revision_only_fixed_bug_is_dropped(self):
        # a patch on a now-FIXED bug (or one we couldn't look up) must never show.
        my_revs = [rev(1, "accepted", bugid=777, title="Bug 777 - landed gtest")]
        fixed = {"777": {"id": 777, "is_open": False, "summary": "Fixed thing"}}
        self.assertEqual(collect.build_my_bugs([], my_revs, NOW, {}, fixed), [])   # closed → dropped
        self.assertEqual(collect.build_my_bugs([], my_revs, NOW, {}, {}), [])      # unverifiable → dropped

    def test_stacked_bug_rolls_up_and_reports_x_of_y(self):
        # a bug with a 2-patch stack (one accepted, one still in review) is NOT
        # ready to land — it's in-review, and carries a 1/2 ready count.
        my_revs = [rev(1, "accepted", bugid=20, reviewers=["PHID-R"]),
                   rev(2, "needs-review", bugid=20, reviewers=["PHID-R"])]
        item = collect.build_my_bugs([bug(id=20)], my_revs, NOW)[0]
        self.assertEqual(item["patch_status"], "in-review")
        self.assertEqual((item["patch_accepted"], item["patch_total"]), (1, 2))

    def test_patch_with_no_reviewer_is_wip_not_in_review(self):
        item = collect.build_my_bugs([bug(id=30)],
                                     [rev(1, "needs-review", bugid=30, reviewers=[])], NOW)[0]
        self.assertEqual(item["patch_status"], "wip")

    def test_assigned_without_patch(self):
        items = collect.build_my_bugs([bug(id=5)], [], NOW)
        self.assertEqual(items[0]["patch_status"], "none")

    def test_meta_bugs_are_excluded(self):
        # a meta/tracking bug is never "my work", assigned or revision-only
        assigned = [bug(id=5, keywords=["meta"]), bug(id=6, keywords=[])]
        my_revs = [rev(1, "accepted", bugid=88)]  # revision on a meta bug
        details = {"88": {"id": 88, "is_open": True, "summary": "Meta thing", "keywords": ["meta"]}}
        ids = {i["id"] for i in collect.build_my_bugs(assigned, my_revs, NOW, {}, details)}
        self.assertEqual(ids, {"6"})   # 5 (meta) + 88 (meta revision-only) both dropped

    def test_is_meta(self):
        self.assertTrue(collect.is_meta(bug(keywords=["meta", "regression"])))
        self.assertFalse(collect.is_meta(bug(keywords=["regression"])))

    def test_user_mybug_item(self):
        # a hand-added bug: real summary + tags, no patch (→ "No patch yet"), marked added
        it = collect.user_mybug_item("555", {"summary": "Pinned bug", "severity": "S2",
                                             "keywords": ["regression"], "is_open": True,
                                             "last_change_time": "2026-07-01T00:00:00Z"}, NOW)
        self.assertEqual((it["id"], it["type"], it["title"]), ("555", "mybug", "Pinned bug"))
        self.assertEqual(it["patch_status"], "none")
        self.assertTrue(it["added"])
        self.assertIn({"text": "S2", "kind": "severity"}, it["tags"])
        self.assertTrue(it["url"].endswith("id=555"))
        # unknown bug (fetch failed) → fallback title, still added
        fb = collect.user_mybug_item("777", None, NOW)
        self.assertEqual(fb["title"], "bug 777")
        self.assertTrue(fb["added"])

    def test_derive_mybug_tags_drops_component_and_low_severity(self):
        tags = collect.derive_mybug_tags(bug(component="Audio/Video: Playback", severity="S2",
                                             keywords=["regression", "crash"], groups=["core-security"]))
        kinds = {(t["kind"], t["text"]) for t in tags}
        self.assertIn(("security", "sec"), kinds)
        self.assertIn(("severity", "S2"), kinds)
        self.assertIn(("regression", "regression"), kinds)
        self.assertIn(("warn", "crash"), kinds)
        self.assertFalse(any(t["kind"] == "component" for t in tags), "component dropped")
        # S3/S4 are the default → dropped
        self.assertEqual(collect.derive_mybug_tags(bug(severity="S3", keywords=[], groups=[])), [])


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
        # re-finalizing must be idempotent — extra_tags don't duplicate
        again = collect.apply_enrichment(enriched, {
            "1": {"extra_tags": [{"text": "ready", "kind": "good"}]}}, NOW)
        self.assertEqual(sum(1 for t in again["sections"]["needinfos"][0]["tags"] if t["text"] == "ready"), 1)

    def test_apply_enrichment_carries_ni_triage_fields(self):
        base = collect.build_base("you@example.com", [bug(id=7, flags=[ni_flag()])],
                                  [], {}, [], [], NOW)
        out = collect.apply_enrichment(base, {"7": {
            "brief": {"bug": "b", "ask": "please investigate the crash"},
            "ask_kind": "investigate", "ready": False, "ready_reason": "no STR",
            "bug_type": "regression", "regressor": "1899123", "duplicate_of": "1902050",
            "meta": "1888000", "priority": "P2", "severity": "S3",
            "missing_info": ["no STR", "no about:support"], "hypothesis": "likely the seek path",
        }}, NOW)
        it = out["sections"]["needinfos"][0]
        self.assertEqual(it["ask_kind"], "investigate")
        self.assertFalse(it["ready"])
        self.assertEqual(it["bug_type"], "regression")           # not clobbering item["type"]=="ni"
        self.assertEqual(it["type"], "ni")
        self.assertEqual(it["regressor"], "1899123")
        self.assertEqual(it["missing_info"], ["no STR", "no about:support"])
        self.assertEqual(it["hypothesis"], "likely the seek path")

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


class TestRevetOverlay(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._prev = os.environ.get("FX_DASHBOARD_DIR")
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["FX_DASHBOARD_DIR"] = self.tmp.name
        self._fetch = collect.fetch_bugs

    def tearDown(self):
        collect.fetch_bugs = self._fetch
        if self._prev is None:
            os.environ.pop("FX_DASHBOARD_DIR", None)
        else:
            os.environ["FX_DASHBOARD_DIR"] = self._prev
        self.tmp.cleanup()

    def test_drops_closed_keeps_open_and_placements(self):
        import store
        store.write_overlay_doc({"items": [{"id": "10"}, {"id": "20"}],
                                 "placements": {"10": "focus", "20": "next"}})
        collect.fetch_bugs = lambda ids, key: {
            "10": {"id": 10, "is_open": True, "summary": "still open"},
            "20": {"id": 20, "is_open": False, "summary": "now fixed"}}
        collect.revet_overlay(NOW)
        doc = store.read_overlay_doc()
        self.assertEqual([i["id"] for i in doc["items"]], ["10"])        # closed 20 dropped
        self.assertEqual(doc["items"][0]["title"], "still open")         # refreshed from bug
        self.assertEqual(doc["placements"], {"10": "focus", "20": "next"})  # placements kept (reopen restores)


class TestFetchBugs(unittest.TestCase):
    class _Resp:
        def __init__(self, body): self._b = body
        def read(self): return self._b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def test_batches_ids_keys_by_str_and_sends_key(self):
        captured = {}

        def fake_urlopen(req, timeout=None):
            captured["url"] = req.full_url
            captured["key"] = req.get_header("X-bugzilla-api-key")
            return self._Resp(json.dumps({"bugs": [{"id": 42, "summary": "S", "is_open": True}]}).encode())

        orig = collect.urllib.request.urlopen
        collect.urllib.request.urlopen = fake_urlopen
        try:
            out = collect.fetch_bugs([42, "43"], "KEY")
        finally:
            collect.urllib.request.urlopen = orig
        self.assertEqual(set(out), {"42"})               # keyed by str id
        self.assertEqual(out["42"]["summary"], "S")
        self.assertIn("id=42%2C43", captured["url"])      # both ids in one batched call
        self.assertEqual(captured["key"], "KEY")

    def test_empty_and_errors_degrade_to_empty(self):
        self.assertEqual(collect.fetch_bugs([], "K"), {})  # nothing to fetch, no call
        def boom(*a, **k): raise RuntimeError("network down")
        orig = collect.urllib.request.urlopen
        collect.urllib.request.urlopen = boom
        try:
            self.assertEqual(collect.fetch_bugs([1], "K"), {})   # never raises
        finally:
            collect.urllib.request.urlopen = orig


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
