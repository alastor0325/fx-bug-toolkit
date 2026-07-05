---
name: dashboard-drain
description: >
  Process the personal dashboard's queued card actions all at once — draft
  needinfo replies, investigate bugs, and review requests you clicked on the
  board — writing the results back for the dashboard to show. Draft-only by
  default (no posts to Bugzilla/Phabricator). Triggers on "/dashboard-drain",
  "process my dashboard queue", "drain the dashboard", "process queued actions".
allowed-tools: [Bash, Read, Write, Agent, mcp__moz__get_bugzilla_bug, mcp__moz__get_phabricator_revision]
---

# Drain the dashboard action queue

When you click a card button on the dashboard (Draft reply · Bug investigate ·
run /bug-start · Run /review), it's appended to a queue file. This skill processes
the whole queue at once and writes results back onto the cards. **Draft-only by
default: never post to Bugzilla/Phabricator** — produce drafts/analyses stored
locally; the user posts anything themselves.

## Step 1 — Locate `drain.py` and read the pending queue

Locate the script (same approach as the other dashboard skills — `${CLAUDE_PLUGIN_ROOT}`
isn't reliable), then list pending actions:

```bash
PY="$(command -v python3 || command -v python)"
[ -z "$PY" ] && { echo "Needs Python 3 (see /init)."; exit 1; }
DRAIN="$("$PY" - <<'PYEOF'
import os, glob
def first(paths):
    for p in paths:
        if p and os.path.isfile(p): return p
    return ""
c = []
root = os.environ.get("CLAUDE_PLUGIN_ROOT")
if root: c.append(os.path.join(root, "dashboard", "drain.py"))
for d in os.environ.get("PATH","").split(os.pathsep):
    d = d.rstrip("/\\")
    if os.path.basename(d) == "bin":
        c.append(os.path.join(os.path.dirname(d), "dashboard", "drain.py"))
hit = first(c)
if not hit:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    m = glob.glob(os.path.join(base, "plugins", "cache", "**", "dashboard", "drain.py"), recursive=True)
    hit = max(m, key=os.path.getmtime) if m else ""
print(hit)
PYEOF
)"
[ -z "$DRAIN" ] && { echo "Could not locate dashboard/drain.py (try /update)."; exit 1; }
echo "drain: $DRAIN"
"$PY" "$DRAIN" list
```

If the list is empty, tell the user there's nothing queued and stop.

## Step 2 — Process each pending action

Each entry is `{ "id", "type", "action", "title", "status", "ts" }`. Handle every
pending one by its `action`. For several entries, **fan out** with the Agent tool
(a subagent per entry) so it's parallel and the main context stays small. Read
sources with `mcp__moz__get_bugzilla_bug(id)` (fall back to `bmo-to-md` for
security bugs) and `mcp__moz__get_phabricator_revision` for `D…` ids.

- **`draft-reply`** (needinfo) — read the bug + the specific needinfo question and
  **draft a reply** that answers it (or asks the right follow-up). Follow the
  `/triage` needinfo-drafting style. Draft only — do not post.
- **`bug-investigate`** (needinfo) — do a focused investigation of the bug (what's
  going on, likely area, what's still unknown). A `gecko-navigator` subagent is a
  good fit. Produce a short findings summary.
- **`bug-start`** (needinfo, offered only when generation marked it solvable) —
  run the `/bug-start` investigation flow to produce a **proposed solution**
  (root cause + fix direction). Summarize it; note where any investigation file
  was written.
- **`review`** — run the `/review` flow on the revision (it writes a structured
  review doc to `$FX_REVIEW_DIR`). Summarize the verdict + top findings and point
  to the doc.

Keep the user's data private: never write an email/API key into results.

## Step 3 — Write results and mark done

Build a results map keyed by `"<id>::<action>"` (matching the queue), each value a
small object the card shows:

```json
{
  "111::draft-reply": { "summary": "Drafted a reply confirming the teardown order is intentional; asks for a profile.", "draft": "<the full drafted reply>" },
  "D9::review": { "summary": "Looks correct; one nit on the null-check placement. Full review: <path>." }
}
```

`summary` is required (shown on the card); include `draft`/other fields as useful.
Write that to a temp file and apply it:

```bash
"$PY" "$DRAIN" apply /path/to/results.json
```

This merges the results into `results.json` and marks those queue entries `done`.

## Step 4 — Hand off

Tell the user what was processed (per action) and that the results are on the
dashboard — refresh, or `/open-dashboard`. Remind them drafts were **not** posted;
they act on them from the cards.

## Notes

- **Draft-only** is the default and the safe path. Posting to BMO/Phabricator is a
  future opt-in mode (like `/triage` reply mode) — not enabled here.
- Follow the fx-bug-toolkit Dev Loop for any change to this skill or `drain.py`.
