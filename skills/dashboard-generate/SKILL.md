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

Data lives **outside the package**, under `$FX_DASHBOARD_DIR` (default
`~/.fx-bug-toolkit/dashboard/`), split per section — `needinfos.json`,
`reviews.json`, `my_bugs.json` (each `{status, generated_at, items}`) — plus a
small `manifest.json`. The server merges them (with your hand-pinned
`my_bugs.user.json`) into the `/data.json` the page fetches, and derives
`/status.json`. All private — **never** put a real email or API key into them,
the enrichment file, or logs (identity comes from env at runtime).

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
DATADIR="${FX_DASHBOARD_DIR:-$HOME/.fx-bug-toolkit/dashboard}"   # where the section files land
echo "data dir: $DATADIR"
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

This fetches the field data and writes the per-section files under `$DATADIR`,
each item carrying its Core tags (component · severity · security · regression)
with `brief`/`solvable` **null**. `my_bugs.json` is display-only, so it's marked
**ready** immediately; `needinfos.json`/`reviews.json` are **running** until you
finalize — an already-open page shows my_bugs live plus "analyzing…" on the other
two (each section has its own status now, so they don't block each other).

## Step 3 — Enrich each item (your reasoning — the LLM half)

Read the base section files (`$DATADIR/needinfos.json`, `$DATADIR/reviews.json` —
each `{status, generated_at, items}`). **Scope the enrichment — do NOT analyze everything**
(real accounts have hundreds of items; enriching all is impractical/expensive):

- **Needinfos AND review requests: only those with `waiting_days <= 7`** (recent).
  Leave older ones **untouched** — they keep `brief: null` and stay in the
  collapsed "not analyzed" ledger. This is the primary, intentional cap.
  - For a **review**, read the revision + its linked bug and produce a brief
    (what the patch does / what to focus a review on) + `extra_tags` (e.g. the
    bug's component, patch size). Reviews split into Direct vs Group on the page
    via the `direct` flag — you don't set that; just brief + tag the recent ones.
- **My-bugs:** leave un-enriched for now.

For each item **in scope**, produce an enrichment entry by **fanning out to the
`dashboard-enrich` sub-agent** — one per item, via the Agent tool with
`subagent_type: "dashboard-enrich"`. That agent is **pinned to Sonnet** in its
frontmatter, so the analysis runs on a cheap model regardless of your session
model (this is read-and-summarize work — do **not** run it on Opus). Pass each
agent the item's `type`, `id`, and `title`; it reads the source
(`mcp__moz__get_bugzilla_bug` / `bmo-to-md` for bugs,
`mcp__moz__get_phabricator_revision` for reviews) and returns that item's
enrichment JSON. Collect the results into the enrichment map (keyed by id).

Run them in parallel/batches so the main context stays small. Do the enrichment
this way — don't inline it into this (possibly Opus) session.

The `dashboard-enrich` agent returns the per-item JSON (see its spec for the full
shape). In brief, keyed by `id`:

- **reviews** → `{ brief: {summary}, extra_tags? }`.
- **needinfos** → a triage-style assessment (mirrors `/triage --analyze-only`):
  - `brief: {bug, ask}` + **`ask_kind`** (`investigate` = the NI asks me to look
    into/diagnose the bug; `easy` = a quick/procedural ask). For `easy`, that's all.
  - For `investigate`: **`ready`** (bug has enough to run `/bug-start`) +
    `ready_reason`; when not ready, **`missing_info`** (concrete gaps as short
    chips); when a root cause is already determinable from artifacts,
    **`hypothesis`** (missing_info OR hypothesis, not both). Optional when evident:
    `bug_type`, `regressor`, `duplicate_of`, `meta`, `priority`, `severity`.
  - This drives the card's button: investigate+ready → **run /bug-start**;
    investigate+not-ready → **draft: request info**; easy → **Draft reply**.

Write the merged map to an enrichment file (a temp path is fine), e.g.:

```json
{
  "1911204": { "brief": {"bug": "...", "ask": "please check why seek crashes"},
               "ask_kind": "investigate", "ready": false, "ready_reason": "no STR",
               "bug_type": "regression", "regressor": "1899123",
               "missing_info": ["no STR", "no about:support"] },
  "1922000": { "brief": {"bug": "...", "ask": "is this still repro on 128?"}, "ask_kind": "easy" },
  "D221450": { "brief": {"summary": "..."}, "extra_tags": [{"text":"large","kind":"info"}] }
}
```

Do **not** invent data you didn't read (omit unsupported fields), and never write
an email/API key into the enrichment.

## Step 4 — Finalize

```bash
"$PY" "$COLLECT" finalize /path/to/enrichment.json
```

Merges the briefs/tags/solvability into the `needinfos.json`/`reviews.json`
section files and flips them to **ready** with a fresh `generated_at`.

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
