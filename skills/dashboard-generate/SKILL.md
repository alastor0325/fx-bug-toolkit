---
name: dashboard-generate
description: >
  Generate the personal dashboard's data — the heavy, triage-style pass that
  fetches your needinfos, review requests, and the bugs you're working on, then
  produces a brief + tags + a solvability gate for each, writing the data file
  the dashboard displays. Run this to (re)build the board; `/open-dashboard`
  just serves the latest result. Triggers on "/dashboard-generate", "generate my
  dashboard", "refresh my dashboard", "rebuild the dashboard".
allowed-tools: [Bash, Read, Write, Agent, mcp__moz__get_bugzilla_bug, mcp__moz__get_phabricator_revision]
---

# Generate the personal dashboard

Two halves, like `/triage`: fast field-gathering in `collect.py` (no LLM), then
**your** enrichment (brief + deep tags + the solvability gate) per item. You write
an enrichment file; `collect.py finalize` merges it and flips the board to ready.
The page never calls Claude — it only displays what this produces.

Data + status live in the dashboard dir: `data.json` (the board) and
`status.json` (running/ready, polled by the page). Both are git-ignored — they
hold your private queue. **Never** put a real email or any API key into them,
into the enrichment file, or into logs (identity comes from env at runtime).

## Step 1 — Locate `collect.py` and check identity

Resolve the script the same robust way the viewer launcher does
(`${CLAUDE_PLUGIN_ROOT}` isn't reliably exported into skill Bash):

```bash
PY="$(command -v python3 || command -v python)"
[ -z "$PY" ] && { echo "Needs Python 3 (see /init)."; exit 1; }
COLLECT="$("$PY" - <<'PYEOF'
import os, glob
def first(paths):
    for p in paths:
        if p and os.path.isfile(p): return p
    return ""
c = []
root = os.environ.get("CLAUDE_PLUGIN_ROOT")
if root: c.append(os.path.join(root, "dashboard", "collect.py"))
for d in os.environ.get("PATH","").split(os.pathsep):
    d = d.rstrip("/\\")
    if os.path.basename(d) == "bin":
        c.append(os.path.join(os.path.dirname(d), "dashboard", "collect.py"))
hit = first(c)
if not hit:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    m = glob.glob(os.path.join(base, "plugins", "cache", "**", "dashboard", "collect.py"), recursive=True)
    hit = max(m, key=os.path.getmtime) if m else ""
print(hit)
PYEOF
)"
[ -z "$COLLECT" ] && { echo "Could not locate dashboard/collect.py — is the plugin installed? (try /update)"; exit 1; }
echo "collect: $COLLECT"
bugzilla-cli whoami 2>/dev/null | head -1
echo "FX_DASHBOARD_USER=${FX_DASHBOARD_USER:-<unset>}"
```

**Identity check — this is a PERSONAL dashboard.** Whose board this builds is
`FX_DASHBOARD_USER` if set, else the owner of `BUGZILLA_API_KEY` (what `whoami`
prints). If `whoami` shows a shared/bot account and `FX_DASHBOARD_USER` is unset,
**stop and tell the user** to set `FX_DASHBOARD_USER` to their Bugzilla email in
`~/.config/secrets/api-keys.env` — otherwise the board would be the bot's work,
not theirs. (Security-restricted needinfos only appear when `BUGZILLA_API_KEY` is
that person's own key. Phabricator sections need `FX_PHABRICATOR_TOKEN`; without
it they're skipped, which is fine.)

## Step 2 — Build the base (fast, no LLM)

```bash
"$PY" "$COLLECT" base
```

This fetches the field data and writes `data.json` with each item's Core tags
(component · severity · security · regression) and `brief`/`solvable` **null**,
and sets `status.json` to **running** — so an already-open page shows "analyzing…".
Sections: `needinfos`, `reviews`, `my_bugs`.

## Step 3 — Enrich each item (your reasoning — the LLM half)

Read the base `data.json`. For **every** item across all three sections, read its
source and produce an enrichment entry. Read sources with the tools you have:
`mcp__moz__get_bugzilla_bug(bug_id)` for bugs (fall back to `bmo-to-md` for
security bugs), `mcp__moz__get_phabricator_revision` for reviews. For many items,
**fan out**: spawn a subagent per item (or per small batch) via the Agent tool so
enrichment runs in parallel and the main context stays small — each returns its
enrichment JSON; you merge them.

Produce, per item, keyed by its `id` (the bug number or `D…` id):

- **`brief`** — a small object the page shows on the card:
  - needinfo → `{ "bug": "1–2 sentences: what the bug is about",
    "ask": "1 sentence: what THIS needinfo is asking of you" }`
  - review → `{ "summary": "1–2 sentences: what the patch does / what to focus a review on" }`
  - my_bug → `{ "summary": "1–2 sentences: current state + the next step" }`
- **`extra_tags`** — optional deeper labels beyond the field tags, each
  `{ "text": "...", "kind": "warn"|"good"|"info" }` — e.g. `needs-STR`,
  `dup-suspect`, `ready`, `waiting-on-reporter`. Keep to what's decision-useful.
- **`solvable`** *(needinfos only)* — `true` only if the bug **already contains
  everything needed to solve it** (clear STR / evident root cause / small scope)
  so `/bug-start` could plausibly produce a fix; else `false`. Add a one-line
  **`solvable_reason`**. This gate decides whether the card offers a
  "looks ready → run /bug-start?" button. Be conservative: default `false` when
  unsure.

Write the merged map to an enrichment file (a temp path is fine), shaped:

```json
{
  "1911204": { "brief": {"bug": "...", "ask": "..."}, "solvable": false,
               "solvable_reason": "needs a repro on 128", "extra_tags": [{"text":"needs-STR","kind":"warn"}] },
  "D221450": { "brief": {"summary": "..."}, "extra_tags": [{"text":"large","kind":"info"}] }
}
```

Do **not** invent data you didn't read, and never write an email/API key into the
enrichment.

## Step 4 — Finalize

```bash
"$PY" "$COLLECT" finalize /path/to/enrichment.json
```

Merges the briefs/tags/solvability into `data.json` and flips `status.json` to
**ready** with a fresh `generated_at`.

## Step 5 — Hand off

Tell the user it's ready and to run **`/open-dashboard`** to view it (or refresh
an open tab). Report a one-line summary: counts per section and how many
needinfos the gate marked solvable.

## Notes

- This is the **generate** half only. Acting on cards (Draft reply / Run /review /
  Run /bug-start) is the separate **drain** step (Phase C) — not done here.
- Re-running regenerates from scratch; it's safe to run as often as you like, but
  it re-reads every item, so it costs time/tokens like `/triage`.
- Follow the fx-bug-toolkit Dev Loop for any change to this skill or `collect.py`.
