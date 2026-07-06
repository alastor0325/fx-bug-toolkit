#!/usr/bin/env python3
"""Gather + shape the dashboard's data (the deterministic half of generation).

The personal dashboard is generated in two halves, mirroring `/triage`:
  1. THIS script (`base`)      — fast, no LLM: fetch field data from Bugzilla +
                                 Phabricator and build the *base* data file with
                                 field-derived tags and `brief`/`solvable` left
                                 null. Writes a status file = "running".
  2. the generate SKILL        — the LLM half: read each item and produce a brief,
                                 deep tags, and the solvability gate, then call
                                 this script's `finalize` to merge that enrichment
                                 in and flip status to "ready".

Then `/open-dashboard` just serves the finished data.json.

    python3 collect.py base                      # write base data + status=running
    python3 collect.py finalize enrichment.json  # merge enrichment, status=ready

Secrets are read from the environment ONLY, never hardcoded, logged, or written
to any output (there's a test enforcing it):
  - BUGZILLA_API_KEY       personal BMO key (bugzilla-cli reads it from the env)
  - FX_PHABRICATOR_TOKEN   Conduit API token
Identity: FX_DASHBOARD_USER (recommended — needinfos/assigned are queryable by
email with any key) else the key owner via `bugzilla-cli whoami`.

The pure transforms + assembly are unit-tested against MOCK backend payloads
(dashboard/tests/test_collect.py) — no network or subprocess in tests.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import store   # dashboard storage layer (paths, atomic writes, per-section files)

DIR = Path(__file__).resolve().parent
PHAB_BASE = os.environ.get("FX_PHABRICATOR_BASE") or "https://phabricator.services.mozilla.com"

BMO_REST = os.environ.get("FX_BUGZILLA_BASE") or "https://bugzilla.mozilla.org"
BMO_SHOW = "https://bugzilla.mozilla.org/show_bug.cgi?id="
SEV_KEYS = frozenset({"S1", "S2", "S3", "S4"})
SEC_KEYWORDS = frozenset({"sec-crit", "sec-high", "sec-moderate", "sec-low"})

# Phabricator revision status → the patch-status shown on a "my bug" card.
PATCH_STATUS = {
    "draft": "wip", "changes-planned": "wip",
    "needs-review": "in-review", "needs-revision": "needs-revision",
    "accepted": "accepted", "published": "landed", "closed": "landed",
}
# A bug can carry a whole STACK of my patches; its stage is rolled up across all
# of them by aggregate_patch(), not read off any single "best" revision.


# ------------------------------------------------------------------ pure helpers

def bmo_url(bug_id) -> str:
    return f"{BMO_SHOW}{bug_id}"


def phab_url(rev_id) -> str:
    return f"{PHAB_BASE}/D{rev_id}"


def parse_whoami(text: str) -> str:
    """Email from `bugzilla-cli whoami` ("Name <email>") or a bare email line."""
    m = re.search(r"<([^>]+@[^>]+)>", text or "")
    if m:
        return m.group(1).strip()
    line = (text or "").strip()
    return line if "@" in line and " " not in line else ""


def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_iso(s):
    if not s:
        return None
    try:
        t = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def age_days(iso, now: datetime) -> int:
    t = _parse_iso(iso)
    return max(0, (now - t).days) if t else 0


def age_days_epoch(epoch, now: datetime) -> int:
    try:
        t = datetime.fromtimestamp(int(epoch), tz=timezone.utc)
    except (ValueError, TypeError, OSError):
        return 0
    return max(0, (now - t).days)


def extract_severity(bug: dict):
    s = (bug.get("severity") or "").strip()
    return s if s in SEV_KEYS else None


def is_meta(bug: dict) -> bool:
    """A tracking/meta bug — we don't work these directly, so they're excluded
    from "My work". Identified by the Bugzilla `meta` keyword (authoritative; the
    "[meta]" title convention isn't relied on)."""
    return "meta" in (bug.get("keywords") or [])


def is_security(bug: dict) -> bool:
    if any(k in SEC_KEYWORDS for k in (bug.get("keywords") or [])):
        return True
    return any("security" in str(g).lower() for g in (bug.get("groups") or []))


def derive_tags(bug: dict) -> list:
    """The Core, field-derived tag set — no LLM. Each tag is {text, kind}; the
    page colors by `kind`. Deeper tags (completeness, solvable, …) are added by
    the generate skill's enrichment, not here."""
    tags = []
    comp = (bug.get("component") or "").strip()
    if comp:
        tags.append({"text": comp, "kind": "component"})
    sev = extract_severity(bug)
    if sev:
        tags.append({"text": sev, "kind": "severity"})
    if is_security(bug):
        tags.append({"text": "sec", "kind": "security"})
    if "regression" in (bug.get("keywords") or []):
        tags.append({"text": "regression", "kind": "regression"})
    return tags


def active_needinfo_flag(bug: dict, user_email: str):
    for f in bug.get("flags") or []:
        if f.get("name") == "needinfo" and f.get("status") == "?" \
                and f.get("requestee") == user_email:
            return f
    return None


def ni_base_item(bug: dict, user_email: str, now: datetime) -> dict:
    """A BMO bug (with flags) → a base needinfo card (brief/solvable filled later
    by the generate skill). `waiting_days` = time since the NI flag was set."""
    flag = active_needinfo_flag(bug, user_email) or {}
    set_date = flag.get("creation_date") or flag.get("modification_date") \
        or bug.get("last_change_time")
    return {
        "type": "ni",
        "id": str(bug["id"]),
        "url": bmo_url(bug["id"]),
        "title": bug.get("summary") or "",
        "waiting_days": age_days(set_date, now),
        "from": flag.get("setter"),
        "tags": derive_tags(bug),
        "brief": None,
        "solvable": None,
    }


def review_requires(rev: dict, mine_phids, names: dict) -> list:
    """The reviewer(s) on `rev` that are me or a review group I'm in — i.e. *why*
    this revision is in my queue. Returns display names (e.g. "#media-playback-
    reviewers", "you"). Reads the `reviewers` attachment. Pure."""
    reviewers = (((rev.get("attachments") or {}).get("reviewers") or {}).get("reviewers")) or []
    mine = mine_phids or set()
    out = []
    for r in reviewers:
        ph = r.get("reviewerPHID")
        if ph in mine:
            nm = (names or {}).get(ph, ph)
            if nm and nm not in out:
                out.append(nm)
    return out


def review_base_item(rev: dict, names: dict, now: datetime, mine_phids=None, my_phid=None) -> dict:
    """A Conduit revision awaiting my (or my group's) review → a base review card.
    `reviewers` lists which of my identities/groups it's requested on; `direct` is
    True when I'm a reviewer personally (vs only via a group)."""
    f = rev.get("fields") or {}
    rid = rev.get("id")
    reviewer_phids = {r.get("reviewerPHID")
                      for r in (((rev.get("attachments") or {}).get("reviewers") or {}).get("reviewers")) or []}
    return {
        "type": "review",
        "id": f"D{rid}",
        "url": phab_url(rid),
        "title": f.get("title") or "",
        "waiting_days": age_days_epoch(f.get("dateModified"), now),
        "author": names.get(f.get("authorPHID")) or "",
        "reviewers": review_requires(rev, mine_phids, names),
        "direct": bool(my_phid) and my_phid in reviewer_phids,
        "tags": [],
        "brief": None,
    }


def patch_status(rev: dict) -> str:
    value = ((rev.get("fields") or {}).get("status") or {}).get("value") or ""
    return PATCH_STATUS.get(value, value or "unknown")


def _rev_bug_id(rev: dict) -> str:
    return str((rev.get("fields") or {}).get("bugzilla.bug-id") or "").strip()


def rev_stage(rev: dict) -> str:
    """One revision's stage, correcting for reviewer presence. Phabricator marks a
    revision "needs-review" the moment it's published — even with NOBODY on it. A
    patch with zero reviewers isn't really in review; it's still WIP (I have to
    request review). So needs-review WITH a reviewer = in-review; WITHOUT = wip."""
    st = patch_status(rev)
    if st == "in-review":
        reviewers = (((rev.get("attachments") or {}).get("reviewers") or {}).get("reviewers")) or []
        return "in-review" if reviewers else "wip"
    return st


def aggregate_patch(revs: list) -> dict:
    """Roll a bug's whole patch STACK up to one stage + an X/Y ready count.

    A bug is only "r+ land it" when EVERY part is accepted — one un-accepted part
    (needs-review, needs-revision, or a no-reviewer wip) means it is NOT ready.
    Precedence, by whose court the ball is in:
      needs-revision — a part bounced back to me → act (r-)
      accepted (all) — every open part is r+ → ready to land
      wip            — a part not yet in review (draft / no reviewer) → my court
      in-review      — parts out for review, waiting on the reviewer
      none           — no open patch
    Landed parts are ignored (done, not pending). Returns {status, accepted,
    total, primary}; `primary` is the revision that set the stage (its reviewer
    name + patch link get shown). Pure."""
    staged = [(r, rev_stage(r)) for r in (revs or [])]
    staged = [(r, s) for (r, s) in staged if s != "landed"]
    total = len(staged)
    accepted = sum(1 for _, s in staged if s == "accepted")
    first = lambda stage: next((r for r, s in staged if s == stage), None)

    if total == 0:
        status, primary = "none", None
    elif any(s == "needs-revision" for _, s in staged):
        status, primary = "needs-revision", first("needs-revision")
    elif accepted == total:
        status, primary = "accepted", first("accepted")
    elif any(s == "wip" for _, s in staged):
        status, primary = "wip", first("wip")
    elif any(s == "in-review" for _, s in staged):
        status, primary = "in-review", first("in-review")
    else:
        status, primary = "wip", staged[0][0]
    return {"status": status, "accepted": accepted, "total": total, "primary": primary}


def rev_reviewer(rev: dict, names: dict) -> str:
    """A display name for who the revision is on (to show 'r- from :X' / 'waiting
    :X'). First resolvable reviewer; '' if none."""
    for r in (((rev.get("attachments") or {}).get("reviewers") or {}).get("reviewers")) or []:
        nm = (names or {}).get(r.get("reviewerPHID"))
        if nm:
            return nm
    return ""


def derive_mybug_tags(bug: dict) -> list:
    """Tags for a bug I OWN — only what changes what I do. Drops the component
    (everything I own is A/V — no signal) and low severities (S3/S4 are the
    default; absence is the signal): keep sec, S1/S2, regression, crash."""
    tags = []
    if is_security(bug):
        tags.append({"text": "sec", "kind": "security"})
    if extract_severity(bug) in ("S1", "S2"):
        tags.append({"text": extract_severity(bug), "kind": "severity"})
    kws = bug.get("keywords") or []
    if "regression" in kws:
        tags.append({"text": "regression", "kind": "regression"})
    if "crash" in kws:
        tags.append({"text": "crash", "kind": "warn"})
    return tags


def _mybug_item(bid, title, last_activity_days, revs, tags, names, assigned=False):
    agg = aggregate_patch(revs or [])
    primary = agg["primary"]
    return {
        "type": "mybug",
        "id": bid,
        "url": bmo_url(bid),
        "title": title,
        "last_activity_days": last_activity_days,
        "patch_status": agg["status"],
        "patch_accepted": agg["accepted"],   # X of X/Y (parts accepted)
        "patch_total": agg["total"],         # Y of X/Y (open parts in the stack)
        "rev_url": phab_url(primary["id"]) if primary else None,
        "reviewer": rev_reviewer(primary, names) if primary else "",
        "is_open": True,                     # collected my_bugs are open by construction
        "assigned": assigned,                # assigned to me? (drives ✕ = demote vs remove)
        "tags": tags,
        "brief": None,
    }


def build_my_bugs(assigned_bugs: list, my_revisions: list, now: datetime,
                  names: dict = None, rev_bug_details: dict = None) -> list:
    """"My work" = union of OPEN bugs assigned to me and OPEN bugs where I have an
    open revision. patch_status is rolled up across the bug's whole patch stack by
    aggregate_patch (r+ only when ALL parts are accepted; a no-reviewer part is
    wip, not in-review), driving the stage: needs-revision/accepted = act,
    in-review = waiting, wip = draft, none = untouched backlog.

    Both halves show the bug's real Bugzilla summary and owned-bug tags. A
    revision-only bug is included ONLY when `rev_bug_details` confirms it's still
    open — a fixed/closed bug (or one we couldn't fetch) is dropped, never shown
    with a stale Phabricator revision title."""
    names = names or {}
    details = rev_bug_details or {}
    revs_by_bug: dict[str, list] = {}
    for r in my_revisions or []:
        bid = _rev_bug_id(r)
        if bid:
            revs_by_bug.setdefault(bid, []).append(r)

    items, seen = [], set()
    for b in assigned_bugs or []:
        bid = str(b["id"])
        seen.add(bid)               # mark seen even if skipped, so revision-only won't re-add
        if is_meta(b):
            continue                 # tracking bug — not worked directly
        items.append(_mybug_item(bid, b.get("summary") or "",
                                 age_days(b.get("last_change_time"), now),
                                 revs_by_bug.get(bid), derive_mybug_tags(b), names, assigned=True))
    # union: bugs I have an open revision on but that aren't assigned to me —
    # only if confirmed still open (and not a meta bug), with the real bug summary.
    for bid, revs in revs_by_bug.items():
        if bid in seen:
            continue
        detail = details.get(bid)
        if not detail or not detail.get("is_open") or is_meta(detail):
            continue  # fixed/closed, meta, or unverifiable → not active work
        last = min((age_days_epoch((r.get("fields") or {}).get("dateModified"), now)
                    for r in revs), default=0)
        items.append(_mybug_item(bid, detail.get("summary") or "", last, revs,
                                 derive_mybug_tags(detail), names))
    return items


def build_base(user_email: str, needinfos: list, reviews: list, review_names: dict,
               assigned: list, my_revisions: list, now: datetime,
               review_mine_phids=None, review_my_phid=None, rev_bug_details=None) -> dict:
    """Assemble the base data file (status "running" — enrichment not done yet).
    Pure; the collector's heart, fully unit-tested against mock backends."""
    return {
        "generated_at": None,
        "user": user_email,
        "status": "running",
        "sections": {
            "needinfos": [ni_base_item(b, user_email, now) for b in (needinfos or [])],
            # exclude my own revisions — a patch I authored isn't a review request
            # OF me (it only matched because I'm in a reviewer group on it)
            "reviews": [review_base_item(r, review_names or {}, now, review_mine_phids, review_my_phid)
                        for r in (reviews or [])
                        if not (review_my_phid and (r.get("fields") or {}).get("authorPHID") == review_my_phid)],
            "my_bugs": build_my_bugs(assigned or [], my_revisions or [], now, review_names, rev_bug_details),
        },
    }


def apply_enrichment(base: dict, enrichment: dict, now: datetime) -> dict:
    """Merge the skill's per-item enrichment ({id: {brief, solvable, extra_tags,
    solvable_reason}}) into the base data and flip status to "ready". Pure."""
    enrichment = enrichment or {}
    for section in (base.get("sections") or {}).values():
        for item in section:
            e = enrichment.get(item.get("id"))
            if not e:
                continue
            if "brief" in e:
                item["brief"] = e["brief"]
            if "solvable" in e:
                item["solvable"] = e["solvable"]
            if e.get("solvable_reason"):
                item["solvable_reason"] = e["solvable_reason"]
            if e.get("extra_tags"):
                # dedup by (text, kind) so re-running finalize is idempotent
                existing = item.setdefault("tags", [])
                have = {(t.get("text"), t.get("kind")) for t in existing}
                for t in e["extra_tags"]:
                    key = (t.get("text"), t.get("kind"))
                    if key not in have:
                        existing.append(t)
                        have.add(key)
    base["status"] = "ready"
    base["generated_at"] = iso_utc(now)
    return base


def status_payload(data: dict, state: str) -> dict:
    """The small status file the page polls to show processing vs loaded."""
    sections = data.get("sections") or {}
    return {
        "state": state,
        "generated_at": data.get("generated_at"),
        "counts": {k: len(v) for k, v in sections.items()},
    }


def conduit_form(params: dict) -> dict:
    """Flatten a nested dict/list into Conduit's `key[sub][0]` form-field names."""
    out: dict[str, str] = {}

    def walk(prefix, val):
        if isinstance(val, dict):
            for k, v in val.items():
                walk(f"{prefix}[{k}]" if prefix else str(k), v)
        elif isinstance(val, (list, tuple)):
            for i, v in enumerate(val):
                walk(f"{prefix}[{i}]", v)
        else:
            out[prefix] = str(val)

    walk("", params)
    return out


# ------------------------------------------------------------------ I/O layer

def run_bugzilla_cli(args: list) -> list:
    r = subprocess.run(["bugzilla-cli", *args, "--json"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"bugzilla-cli {' '.join(args)} failed: {r.stderr.strip()}")
    return json.loads(r.stdout or "[]")


def fetch_bugs(ids, api_key: str) -> dict:
    """Batch-fetch canonical bug fields (summary, open/closed, severity, keywords,
    groups) for the given bug IDs from the BMO REST API — bugzilla-cli's `get` has
    no --json/batch. Used to vet revision-only bugs: we only surface ones we can
    confirm are still open, with the bug's real summary (never a Phabricator
    revision title, never a fixed bug). Returns {str(id): bug}; {} on any error
    (callers treat a missing bug as 'don't show it'). Never raises."""
    ids = [str(i) for i in (ids or []) if str(i).strip()]
    if not ids:
        return {}
    try:
        q = urllib.parse.urlencode({
            "id": ",".join(ids),
            "include_fields": "id,summary,is_open,severity,keywords,groups,last_change_time",
        })
        req = urllib.request.Request(f"{BMO_REST}/rest/bug?{q}",
                                     headers={"X-BUGZILLA-API-KEY": api_key or ""})
        with urllib.request.urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read())
        return {str(b.get("id")): b for b in (payload.get("bugs") or [])}
    except Exception as e:  # noqa: BLE001 — degrade gracefully, never crash generation
        print(f"warning: bug detail fetch skipped ({e})", file=sys.stderr)
        return {}


def conduit(method: str, params: dict, token: str) -> dict:
    form = conduit_form({**params, "api.token": token})
    data = urllib.parse.urlencode(form).encode()
    req = urllib.request.Request(f"{PHAB_BASE}/api/{method}", data=data)
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.loads(resp.read())
    if payload.get("error_code"):
        raise RuntimeError(f"conduit {method}: {payload.get('error_info')}")
    return payload.get("result") or {}


def fetch_phabricator(token: str):
    """Return (reviews, review_names, my_revisions, mine_phids) or empties on any
    error — the dashboard still renders the Bugzilla half. Never raises.

    Reviews include revisions requested on a **review group I'm a member of**
    (e.g. #media-playback-reviewers), not just ones assigned to me directly — a
    revision is mine to review if any of {me, my groups} is a reviewer."""
    try:
        me = conduit("user.whoami", {}, token)
        phid = me.get("phid")
        if not phid:
            return [], {}, [], set(), None
        names = {phid: me.get("userName") or "you"}
        # review groups (projects) I'm a member of
        groups = (conduit("project.search", {"constraints": {"members": [phid]}}, token)
                  .get("data") or [])
        group_phids = []
        for g in groups:
            gp = g.get("phid")
            if not gp:
                continue
            group_phids.append(gp)
            gf = g.get("fields") or {}
            names[gp] = "#" + (gf.get("slug") or gf.get("name") or "group")
        mine_phids = set([phid] + group_phids)

        reviews = (conduit("differential.revision.search",
                           {"constraints": {"reviewerPHIDs": [phid] + group_phids,
                                            "statuses": ["needs-review"]},
                            "attachments": {"reviewers": 1}}, token)
                   .get("data") or [])
        my_revs = (conduit("differential.revision.search",
                           {"constraints": {"authorPHIDs": [phid],
                                            "statuses": ["draft", "needs-review",
                                                         "needs-revision", "accepted",
                                                         "changes-planned"]},
                            "attachments": {"reviewers": 1}}, token)
                   .get("data") or [])
        # resolve user names for review authors + all reviewer users (reviews +
        # my_revs) — so cards can say "r- from :padenot" / "waiting :bryce"
        user_phids = set()
        for r in reviews:
            ap = (r.get("fields") or {}).get("authorPHID")
            if ap:
                user_phids.add(ap)
        for r in list(reviews) + list(my_revs):
            for rv in (((r.get("attachments") or {}).get("reviewers") or {}).get("reviewers")) or []:
                ph = rv.get("reviewerPHID")
                if ph and ph.startswith("PHID-USER-"):
                    user_phids.add(ph)
        if user_phids:
            users = conduit("user.search", {"constraints": {"phids": sorted(user_phids)}}, token)
            for u in users.get("data") or []:
                f = u.get("fields") or {}
                names[u.get("phid")] = f.get("username") or f.get("realName") or ""
        return reviews, names, my_revs, mine_phids, phid
    except Exception as e:  # noqa: BLE001 — degrade gracefully, never crash generation
        print(f"warning: Phabricator collection skipped ({e})", file=sys.stderr)
        return [], {}, [], set(), None


def write_json(path: Path, data) -> None:
    """Atomic JSON write (temp + os.replace) so a polling reader never sees a torn
    file. Thin wrapper over the storage layer."""
    store.atomic_write_json(Path(path), data)


def user_mybug_item(bid, detail: dict, now: datetime) -> dict:
    """A minimal "my work" item for a bug the USER pinned by hand. No Phabricator
    lookup (patch_status "none" → it shows under "No patch yet"); a later collector
    run fills in real patch status if the bug turns out to be mine. The add is
    honored even for a meta/closed bug — the user asked for it on purpose."""
    detail = detail or {}
    return {
        "type": "mybug", "id": str(bid), "url": bmo_url(bid),
        "title": detail.get("summary") or f"bug {bid}",
        "last_activity_days": age_days(detail.get("last_change_time"), now),
        "patch_status": "none", "patch_accepted": 0, "patch_total": 0,
        "rev_url": None, "reviewer": "",
        "tags": derive_mybug_tags(detail),
        "is_open": detail.get("is_open", True),
        "assigned": False,   # a hand-pinned bug; ✕ removes it (vs demote for assigned)
        "added": True, "brief": None,
    }


def resolve_user_email(whoami_run=None) -> str:
    """Whose dashboard this is. Prefer explicit FX_DASHBOARD_USER (needinfos and
    assigned bugs are queryable by email with any key — the key only gates
    visibility of security-restricted bugs), else the key owner via whoami."""
    explicit = (os.environ.get("FX_DASHBOARD_USER") or "").strip()
    if explicit:
        return explicit
    run = whoami_run or (lambda: subprocess.run(
        ["bugzilla-cli", "whoami"], capture_output=True, text=True))
    who = run()
    return parse_whoami(who.stdout) if who.returncode == 0 else ""


def cmd_base() -> int:
    now = datetime.now(timezone.utc)
    user_email = resolve_user_email()
    if not user_email:
        print("error: could not determine whose dashboard to build. Set "
              "FX_DASHBOARD_USER to your Bugzilla email, or ensure BUGZILLA_API_KEY "
              "is set so `bugzilla-cli whoami` works.", file=sys.stderr)
        return 1

    needinfos = run_bugzilla_cli(["needinfos", "--user", user_email])
    assigned = run_bugzilla_cli(["assigned", "--user", user_email])

    token = os.environ.get("FX_PHABRICATOR_TOKEN") or ""
    if token:
        reviews, names, my_revs, mine_phids, my_phid = fetch_phabricator(token)
    else:
        print("warning: FX_PHABRICATOR_TOKEN not set — skipping Phabricator "
              "(reviews + patch status).", file=sys.stderr)
        reviews, names, my_revs, mine_phids, my_phid = [], {}, [], set(), None

    # revision-only bugs (I have a patch, not assigned to me) need a Bugzilla
    # lookup for their real summary + open/closed state — otherwise a fixed bug
    # would leak in under its Phabricator revision title.
    assigned_ids = {str(b.get("id")) for b in assigned}
    rev_only_ids = {_rev_bug_id(r) for r in my_revs} - assigned_ids - {""}
    rev_bug_details = fetch_bugs(sorted(rev_only_ids), os.environ.get("BUGZILLA_API_KEY") or "")

    base = build_base(user_email, needinfos, reviews, names, assigned, my_revs, now,
                      mine_phids, my_phid, rev_bug_details)
    now_iso = iso_utc(now)
    secs = base["sections"]
    # Split per section: my_bugs is display-only (no LLM) → ready immediately;
    # needinfos/reviews still need the brief pass → running until finalize. Each
    # is its own atomic file, so a later regen can touch one without the others.
    store.write_section("needinfos", secs["needinfos"], "running", now_iso)
    store.write_section("reviews", secs["reviews"], "running", now_iso)
    store.write_section("my_bugs", secs["my_bugs"], "ready", now_iso)
    store.atomic_write_json(store.manifest_path(), {
        "user": user_email, "sections": list(store.SECTIONS),
        "schema": store.SCHEMA, "generated_at": now_iso})
    revet_overlay(now)   # drop any hand-pinned bug that has since closed
    print(f"wrote base to {store.data_dir()} — {len(secs['needinfos'])} NI, "
          f"{len(secs['reviews'])} reviews, {len(secs['my_bugs'])} my-bugs")
    return 0


def revet_overlay(now: datetime) -> None:
    """Re-check hand-pinned bugs against Bugzilla and drop any that have closed
    (closed bugs are always removed from My work). Placements are left intact so a
    reopened bug returns to its chosen section. Never raises."""
    doc = store.read_overlay_doc()
    items = doc.get("items") or []
    if not items:
        return
    details = fetch_bugs([i.get("id") for i in items], os.environ.get("BUGZILLA_API_KEY") or "")
    if not details:
        return  # couldn't verify (no key / offline) — leave the overlay as-is
    kept = []
    for it in items:
        d = details.get(str(it.get("id")))
        if d is None:
            kept.append(it)              # not returned (restricted?) — keep, don't guess
        elif d.get("is_open"):
            kept.append(user_mybug_item(it.get("id"), d, now))  # refresh title/tags
    if len(kept) != len(items):
        doc["items"] = kept
        store.write_overlay_doc(doc)


def cmd_finalize(enrichment_path: str) -> int:
    now = datetime.now(timezone.utc)
    enrichment = json.loads(Path(enrichment_path).read_text(encoding="utf-8")) if enrichment_path else {}
    # rebuild the combined shape from the per-section files, merge the enrichment,
    # then write each section back as ready.
    base = {"sections": {k: store.read_section(k).get("items") or [] for k in store.SECTIONS},
            "generated_at": None, "status": "running"}
    data = apply_enrichment(base, enrichment, now)
    now_iso = data["generated_at"]
    for k in store.SECTIONS:
        store.write_section(k, data["sections"][k], "ready", now_iso)
    m = store.read_manifest()
    m["generated_at"] = now_iso
    m.setdefault("schema", store.SCHEMA)
    store.atomic_write_json(store.manifest_path(), m)
    print(f"finalized {store.data_dir()} (status: ready)")
    return 0


def main(argv: list) -> int:
    cmd = argv[1] if len(argv) > 1 else "base"
    if cmd == "base":
        return cmd_base()
    if cmd == "finalize":
        return cmd_finalize(argv[2] if len(argv) > 2 else "")
    print(f"usage: {argv[0]} base | finalize <enrichment.json>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
