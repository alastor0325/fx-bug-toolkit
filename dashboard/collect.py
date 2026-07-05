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

DIR = Path(__file__).resolve().parent
OUT = Path(os.environ.get("FX_DASHBOARD_DATA_OUT") or (DIR / "data.json"))
STATUS_OUT = Path(os.environ.get("FX_DASHBOARD_STATUS_OUT") or (DIR / "status.json"))
PHAB_BASE = os.environ.get("FX_PHABRICATOR_BASE") or "https://phabricator.services.mozilla.com"

BMO_SHOW = "https://bugzilla.mozilla.org/show_bug.cgi?id="
SEV_KEYS = frozenset({"S1", "S2", "S3", "S4"})
SEC_KEYWORDS = frozenset({"sec-crit", "sec-high", "sec-moderate", "sec-low"})

# Phabricator revision status → the patch-status shown on a "my bug" card.
PATCH_STATUS = {
    "draft": "wip", "changes-planned": "wip",
    "needs-review": "in-review", "needs-revision": "needs-revision",
    "accepted": "accepted", "published": "landed", "closed": "landed",
}
# Which patch status to surface when a bug has several of my revisions: the one
# that most wants my attention first.
_PATCH_RANK = {"needs-revision": 5, "accepted": 4, "in-review": 3, "wip": 2, "landed": 1}


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


def best_patch_status(revs: list) -> str:
    """Of a bug's several revisions of mine, the status that most wants attention."""
    statuses = [patch_status(r) for r in revs]
    return max(statuses, key=lambda s: _PATCH_RANK.get(s, 0)) if statuses else "none"


def build_my_bugs(assigned_bugs: list, my_revisions: list, now: datetime) -> list:
    """The "bugs I'm working on" section = union of bugs assigned to me and bugs
    where I have an open revision. Assigned bugs carry full field tags; a bug that
    only shows up via a revision gets limited info from the revision. Each item
    gets its patch_status from my most-attention-worthy revision on it."""
    revs_by_bug: dict[str, list] = {}
    for r in my_revisions or []:
        bid = _rev_bug_id(r)
        if bid:
            revs_by_bug.setdefault(bid, []).append(r)

    items, seen = [], set()
    for b in assigned_bugs or []:
        bid = str(b["id"])
        seen.add(bid)
        revs = revs_by_bug.get(bid)
        items.append({
            "type": "mybug",
            "id": bid,
            "url": bmo_url(bid),
            "title": b.get("summary") or "",
            "age_days": age_days(b.get("last_change_time"), now),
            "patch_status": best_patch_status(revs) if revs else "none",
            "tags": derive_tags(b),
            "brief": None,
        })
    # union: bugs I have a revision on but that aren't assigned to me (limited
    # info — no BMO fields fetched here; the brief/tags come from enrichment)
    for bid, revs in revs_by_bug.items():
        if bid in seen:
            continue
        title = (revs[0].get("fields") or {}).get("title") or ""
        items.append({
            "type": "mybug",
            "id": bid,
            "url": bmo_url(bid),
            "title": title,
            "age_days": min((age_days_epoch((r.get("fields") or {}).get("dateModified"), now)
                             for r in revs), default=0),
            "patch_status": best_patch_status(revs),
            "tags": [],
            "brief": None,
        })
    return items


def build_base(user_email: str, needinfos: list, reviews: list, review_names: dict,
               assigned: list, my_revisions: list, now: datetime,
               review_mine_phids=None, review_my_phid=None) -> dict:
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
            "my_bugs": build_my_bugs(assigned or [], my_revisions or [], now),
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
                                                         "changes-planned"]}}, token)
                   .get("data") or [])
        author_phids = sorted({(r.get("fields") or {}).get("authorPHID")
                               for r in reviews if (r.get("fields") or {}).get("authorPHID")})
        if author_phids:
            users = conduit("user.search", {"constraints": {"phids": author_phids}}, token)
            for u in users.get("data") or []:
                f = u.get("fields") or {}
                names[u.get("phid")] = f.get("username") or f.get("realName") or ""
        return reviews, names, my_revs, mine_phids, phid
    except Exception as e:  # noqa: BLE001 — degrade gracefully, never crash generation
        print(f"warning: Phabricator collection skipped ({e})", file=sys.stderr)
        return [], {}, [], set(), None


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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

    base = build_base(user_email, needinfos, reviews, names, assigned, my_revs, now, mine_phids, my_phid)
    write_json(OUT, base)
    write_json(STATUS_OUT, status_payload(base, "running"))
    print(f"wrote base {OUT} — {len(base['sections']['needinfos'])} NI, "
          f"{len(base['sections']['reviews'])} reviews, "
          f"{len(base['sections']['my_bugs'])} my-bugs (status: running)")
    return 0


def cmd_finalize(enrichment_path: str) -> int:
    now = datetime.now(timezone.utc)
    base = json.loads(OUT.read_text(encoding="utf-8"))
    enrichment = json.loads(Path(enrichment_path).read_text(encoding="utf-8")) if enrichment_path else {}
    data = apply_enrichment(base, enrichment, now)
    write_json(OUT, data)
    write_json(STATUS_OUT, status_payload(data, "ready"))
    print(f"finalized {OUT} (status: ready)")
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
