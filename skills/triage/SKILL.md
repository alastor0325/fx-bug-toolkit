---
name: triage
description: Firefox A/V weekly bug triage — completeness check, duplicate detection, P/S assessment, needinfo drafting, and meta-bug blocking across watched + recent bugs, writing pending drafts the triage dashboard reads. Triggers on "/triage", "triage <bug-id>", "triage <bugzilla-url>", "triage Firefox bugs", "weekly triage".
allowed-tools: [Bash, Read, Write, Edit, Agent, AskUserQuestion]
---

# /triage Skill — Firefox A/V Weekly Bug Triage

Use this skill during weekly Firefox Audio/Video bug triage duty. It handles
information completeness, duplicate detection, P/S assessment, NI drafting, and
meta-bug blocking. All BMO I/O goes through `bugzilla-cli` — never call the REST
API directly.

**Setup — `$TRIAGE_OWNER` (required):** the **triage owner** (the person
responsible for the §1b "ready for implementation" bugs) can opt into being CC'd
and/or needinfo'd on a draft via the dashboard's **"CC me" / "NI me"** checkboxes
— **default off**, decided per bug. The skill does **not** auto-CC/NI the owner;
it just leaves `cc_add`/`ni_targets` for those toggles to populate. `TRIAGE_OWNER`
is that Bugzilla email (yours, if you run triage) — required so the toggles know
whom to add. The **first time you run `/triage`**
the Setup check explicitly resolves it: if `$TRIAGE_OWNER` is unset it **asks you
for the email and persists it** before any triage work begins (see Setup check).
`bugzilla-cli` (BMO I/O) and a configured triage data dir (`$TRIAGE_DIR`, default
`~/firefox-triage/`) are also required — see Setup check.

**Setup — `$TRIAGE_COMPONENTS` (optional, has a default):** the set of Bugzilla
components `/triage` covers. The **default eight A/V components** are defined in
[`components.md`](components.md) — the single source of truth (the skill, the
meta-bug search, and `bugzilla-cli fetch` are all driven from it; the CLI no
longer hardcodes the set). On the **first run**, the Setup check shows that
default list and asks whether to keep it or customize it, then persists the
choice (see Setup check → Resolve `$TRIAGE_COMPONENTS`). Unset = the default set.

## Invocation forms

- `/triage` — **full session**: poll all watched bugs + fetch new bugs from the last 14 days + triage all
- `/triage <bug-id>` — **single-bug mode**: triage exactly one bug; MUST NOT touch any other bug or any other pending/watch/log state
- `/triage <bugzilla-url>` — **batch mode**: parse all bug IDs from the URL; run single-bug mode for each ID independently

### Mode isolation rules

**Single-bug mode (`/triage <id>`) is strictly isolated:**
- Do NOT run `bugzilla-cli watch-poll` (which operates on all watched bugs)
- Do NOT run `bugzilla-cli fetch` (which fetches other new bugs)
- Do NOT read or write `pending/` files for any other bug ID
- Do NOT append entries for other bugs to `triage-log.json`
- Do NOT call `/firefox-wiki:add` for new patterns (orchestrator handles this after all agents finish)
- Only allowed side effects: `pending/bug-<id>.json`, one `triage-log.json` entry for `<id>`, one `watch-add`/`watch-remove` for `<id>`

To check for a reply on a specific watched bug in single-bug mode, fetch it directly:
```bash
bugzilla-cli get <id>
```
Then inspect comments and flags manually against the watch entry — do not invoke `watch-poll`.

---

## Triage scope — components

Only triage bugs in the **configured component set**. Skip anything else (note
"out of scope" and move on).

The component set is resolved in the Setup check into `$TRIAGE_COMPONENTS`
(see Setup check → Resolve `$TRIAGE_COMPONENTS`). The canonical default list and
the override mechanism live in [`components.md`](components.md) — that doc is the
single source of truth; do not maintain a competing list here. The **default
eight** (used when `$TRIAGE_COMPONENTS` is unset) are:

- `Audio/Video`
- `Audio/Video: cubeb`
- `Audio/Video: GMP`
- `Audio/Video: MediaStreamGraph`
- `Audio/Video: Playback`
- `Audio/Video: Recording`
- `Web Audio`
- `Audio/Video: Web Codecs`

Throughout this skill, "the configured components" / "the components listed
above" means the resolved `$TRIAGE_COMPONENTS` set, not a fixed eight.

---

## Setup check

`/triage` needs the `bugzilla-cli` binary for all Bugzilla I/O. Verify it's
installed; if missing, install the version this plugin targets:
```bash
bugzilla-cli --version 2>/dev/null || echo "NOT FOUND"
```
If not found: "Run `cargo install --git https://github.com/alastor0325/bugzilla-cli --tag v0.2.0`." (Needs `cargo` — see `/init`.)

### Mode — reply vs read-only

`/triage` runs in one of two modes:

- **Reply mode** — posts comments, sets needinfo, and updates fields on apply.
  Needs a BMO API key (`bugzilla-cli` configured for writes) and `$TRIAGE_OWNER`.
- **Read-only mode (default)** — fetches bugs and drafts every action, but makes
  **no Bugzilla writes**. Needs no API key and no `$TRIAGE_OWNER`. Reads run
  anonymously, so **security-restricted bugs are not visible**.

Resolve the mode — **if a key is already configured, that *is* reply mode** (don't
ask); otherwise ask:
```bash
if [ -n "$BUGZILLA_BOT_API_KEY" ] || bugzilla-cli whoami >/dev/null 2>&1; then
  echo "MODE=reply"
else
  echo "MODE=ask"
fi
```

- **`MODE=reply`** — run in **reply mode**. Cache the email from `bugzilla-cli
  whoami` as `$BOT_EMAIL` (used wherever the skill refers to the "bot account":
  NI targets, ACTIONS blocks, pending JSON).
- **`MODE=ask`** — no key configured. Ask with `AskUserQuestion` whether to enable
  reply mode:
  - **Read-only (recommended default)** — proceed read-only. There is no
    `$BOT_EMAIL`; **skip every Bugzilla write** — produce the pending drafts and
    the dashboard view, but do **not** run `apply`/`post-comment`/`set-ni`/
    `set-fields`, and do **not** require `$TRIAGE_OWNER`. Tell the user the drafts
    are reviewable but won't be written back until they enable reply mode
    (`bugzilla-cli setup`).
  - **Enable reply mode** — run `bugzilla-cli setup` (choose write mode, provide a
    key), then re-run `bugzilla-cli whoami`, cache `$BOT_EMAIL`, and continue in
    reply mode.

### Resolve `$TRIAGE_OWNER` (reply mode only)

**Read-only mode skips this entirely** (no writes ⇒ no owner needed). In **reply
mode** the skill CCs/needinfo's the triage owner on writes, so it **must not
proceed without `$TRIAGE_OWNER`.** Resolve it before any triage work:

```bash
echo "TRIAGE_OWNER=${TRIAGE_OWNER:-<unset>}"
```

- **If set:** cache the value as `$TRIAGE_OWNER` for the session and continue.
- **If `<unset>` (first run):** do **not** silently default it. Ask the user for
  the triage owner's Bugzilla email with `AskUserQuestion` — offer `$BOT_EMAIL`
  (from `whoami` above) as the recommended option (most people triage their own
  bugs), plus an "Other" free-text option for a different address. Then **persist
  it** so future non-interactive skill shells pick it up, and export it for the
  current session:

  ```bash
  # Append to the file non-interactive bash reads (see /init); create it if absent.
  echo 'export TRIAGE_OWNER="<chosen-email>"' >> ~/.fx-bug-toolkit.env.sh
  export TRIAGE_OWNER="<chosen-email>"
  ```

  On macOS/Linux zsh, `~/.zshenv` is the equivalent non-interactive file; mirror
  the `export` there if that's what the user's shell reads. Confirm to the user
  which file you wrote and that the value is now set, then continue. Never run
  triage with an empty or placeholder `$TRIAGE_OWNER`.

### Resolve `$TRIAGE_COMPONENTS` (optional — has a default)

The component set drives `bugzilla-cli fetch`, the meta-bug search, and the
pre-flight scope filter. The canonical default list and the override mechanism
live in [`components.md`](components.md). Resolve the set before fetching:

```bash
echo "TRIAGE_COMPONENTS=${TRIAGE_COMPONENTS:-<unset>}"
```

- **If set:** it is a `;`-separated list of exact Bugzilla component names. Cache
  it for the session and split on `;` into the component list.
- **If `<unset>` (first run):** default to the eight components in
  [`components.md`](components.md). Show that default list to the user and ask
  with `AskUserQuestion` whether to **keep the default** (recommended) or
  **customize** it (free-text "Other": a `;`-separated list of exact component
  names). This is optional — keeping the default is the common case. Then:
  - **Kept default:** do **not** write `$TRIAGE_COMPONENTS` (unset = default; the
    skill stays self-updating if the default list ever changes). Just confirm the
    eight components that will be triaged.
  - **Customized:** persist and export the chosen list (same env file as
    `$TRIAGE_OWNER`):
    ```bash
    echo 'export TRIAGE_COMPONENTS="Comp A;Comp B;Comp C"' >> ~/.fx-bug-toolkit.env.sh
    export TRIAGE_COMPONENTS="Comp A;Comp B;Comp C"
    ```
    Confirm which file you wrote and the exact set that will be triaged.

**Always print the resolved component list to the user before any fetch**, so it
is unambiguous which components this run covers — e.g.
`Triaging components: Audio/Video, Audio/Video: GMP, Web Audio`.

**Building `bugzilla-cli` flags from the resolved set.** Wherever a command needs
`--component` flags (the meta search below, and `fetch`), expand the resolved set
into one `--component "<name>"` flag per component. Read the value first
(`echo "${TRIAGE_COMPONENTS:-...}"`), then emit a literal flag per entry — do not
rely on shell array splitting (it differs between bash and zsh). When
`$TRIAGE_COMPONENTS` is unset, expand the eight defaults shown below.

Then refresh the live meta bug list (one `--component` flag per resolved
component; the default eight shown here — substitute the configured set if
customized):
```bash
bugzilla-cli search "[meta]" \
  --component "Audio/Video" \
  --component "Audio/Video: cubeb" \
  --component "Audio/Video: GMP" \
  --component "Audio/Video: MediaStreamGraph" \
  --component "Audio/Video: Playback" \
  --component "Audio/Video: Recording" \
  --component "Web Audio" \
  --component "Audio/Video: Web Codecs" \
  --limit 200
```

Cache this result as `$META_BUGS` for the session. In Step 4b, match against `$META_BUGS`
first (live data), then fall back to the static table below if the query failed.

---

## Downloads

Never auto-download anything (bug attachments, media samples, test fixtures,
profiles, screen recordings). Whenever any step — including a parallel triage
sub-agent or the Process-queue drain — needs a file pulled to disk, **follow the
`/download-guard` rule**: it presents a Yes/No `AskUserQuestion` per file and, on
Yes, fetches into the one shared folder `~/.cache/firefox-download-guard/`. That
rule owns the temp folder and its pruning (>30 days, on every invocation) — do
not manage downloads or call `curl`/`wget`/`yt-dlp` here directly.

---

## Knowledge base

Two files in `~/firefox-triage/knowledge/` accumulate triage knowledge across sessions.

### Triage patterns (Firefox Knowledge Wiki)

Triage patterns live in the Firefox Knowledge Wiki under `triage/`. Look them up at the
start of every session using:

```
/firefox-wiki:lookup triage patterns
```

This surfaces pages like `triage/ai-advised-pref-changes`, `triage/wrong-component-graphics-routing`,
`triage/ffvpx-hw-decode-codec-support`, `triage/chrome-ua-assume-firefox`, etc.

When you observe a new pattern worth remembering, use `/firefox-wiki:add` to record it as a
`triage/<slug>.md` page — never write directly to files. Include a source citation (bug number
or user feedback + date).

### triage-log.json

Append one entry per triaged bug immediately after each `apply {id}` or `skip {id}`. Read the existing file first, append the new entry, write it back.

```json
[
  {
    "bug_id": 2028507,
    "date": "2026-04-03",
    "component": "Audio/Video: Playback",
    "reporter": "user@example.com",
    "decision": "ni_sent",
    "reason": "Missing STR and about:support",
    "priority": null,
    "severity": null
  }
]
```

`decision` values: `ni_sent`, `triaged`, `duplicate`, `invalid`, `wrong_component`, `incomplete`, `stalled`, `skipped`.

---

## Poll watched bugs (reply monitor) — full session only

**Only run in full `/triage` mode.** Skip entirely for `/triage <id>` and `/triage <url>`.**

Before fetching new bugs, always run:
```bash
bugzilla-cli watch-poll
```

Process the five buckets in order:

| Bucket | Meaning | Action |
|---|---|---|
| `replied` | NI target posted a comment after the NI was set | Re-enter the 6-step workflow from Step 1 |
| `ni_cleared` | NI flag was cleared without a comment (e.g. answered off-channel) | Re-enter the 6-step workflow from Step 1 |
| `stale` | No reply after 14 days, NI still active | Propose INCOMPLETE; draft a comment noting no response |
| `auto_removed` | No reply after 30 days; purged from watch list | Log only — no action needed |
| `inaccessible` | Bug fetch failed (deleted or moved to security group) | Log warning only |

Handle all watch-poll bugs before processing new fetched bugs.

**`ni_cleared` does NOT mean the reporter answered — determine whether you're
still awaiting.** Before concluding a bug is ready, verify **who** the cleared NI
was on and whether the party you actually need has responded:

- If the NI was misdirected (e.g. a self-NI on the triage owner/the bot instead of the
  reporter), the reporter was never prompted — **you're still awaiting them.**
  Correct the NI target to the reporter; the bug then belongs in **Awaiting**
  (keep it on the watch list, NI'd on the reporter), **not** a fresh §1a
  needs-info draft. The question is already posted (in the existing comment);
  only the NI target was wrong. A §1a draft is for *posing a new or missing
  question* — once the ask is out and correctly targeted, the bug is Awaiting,
  not an actionable needs-info item.
- Never set a self-NI on the triage owner (§1b) while the comment asks the reporter to try
  something and report back — a "please try X and tell us the result" comment is
  an §1a ask and the NI must go on the reporter.

**The general test — "are we still awaiting?"** A bug is *still Awaiting* (keep
it watched, write **no** needs-info draft) whenever the party you need (usually
the reporter) has an active, correctly-targeted NI and has not *substantively*
responded — regardless of whether watch-poll surfaced it via `replied` (a
non-substantive comment, e.g. a co-owner re-asking the reporter) or `ni_cleared`
(a misdirected NI now corrected). Only leave Awaiting when that party
substantively responds (see the substantive-vs-non-substantive gate in §1a).

### When does poll run?

`watch-poll` runs only when you manually invoke `/triage`. Replies accumulate
silently until then — nothing is missed, but you won't know about them until the
next session. (You can automate this with your own scheduler running
`claude … -p "/triage"`, but that's outside this skill.)

---

## Fetch bugs

**Full session (`/triage`):** pass the resolved component set (from Setup check →
Resolve `$TRIAGE_COMPONENTS`) as one `--component "<name>"` flag per component —
`fetch` owns no built-in list when the caller supplies it. The default eight are
shown here; substitute the configured set if customized:
```bash
START=$(date -v-14d +%Y-%m-%d 2>/dev/null || date -d '14 days ago' +%Y-%m-%d)
bugzilla-cli fetch --start $START \
  --component "Audio/Video" \
  --component "Audio/Video: cubeb" \
  --component "Audio/Video: GMP" \
  --component "Audio/Video: MediaStreamGraph" \
  --component "Audio/Video: Playback" \
  --component "Audio/Video: Recording" \
  --component "Web Audio" \
  --component "Audio/Video: Web Codecs"
```
Parse the JSON array. Process bugs oldest-first.

**Single-bug mode (`/triage <id>` or each ID in `/triage <url>`):**
```bash
bugzilla-cli get <id>
```
This is the only fetch allowed. Do not call `fetch` or `watch-poll`.

---

## Parallel dispatch — full session only

After collecting the combined bug list (watch-poll hits + new fetched bugs), dispatch
all bugs **simultaneously** using background agents — one agent per bug. Do this in a
**single message** so all agents launch at the same time.

### Orchestrator steps

1. **Collect all bug IDs** from watch-poll output + fetch output into one deduplicated list.

2. **Spawn one background Agent per bug** (all in a single message, `run_in_background: true`):

   Use this prompt for each agent (substitute `{id}`):
   ```
   You are running single-bug Firefox A/V triage for bug {id}.

   Follow the fx-bug-toolkit /triage single-bug workflow (run `/triage {id}`):
   pre-flight skip check → 6-step workflow → §1a/§1b/§1c branch.

   PARALLEL MODE — these rules override normal behaviour:
   - Write your triage-log entry to ~/firefox-triage/triage-log-tmp-{id}.json
     (a single-element JSON array) instead of appending to triage-log.json directly.
   - If watch-add is needed, write ~/firefox-triage/watch-tmp-{id}.json:
       {"bug_id": {id}, "title": "...", "ni_targets": ["email@example.com"]}
     Do NOT call bugzilla-cli watch-add directly.
   - Do NOT call /firefox-wiki:add (orchestrator handles new patterns after all agents finish).
   - pending/bug-{id}.json: write as normal.
   - **NO direct Bugzilla writes** — do NOT call post-comment, set-ni, set-fields, or any
     bugzilla-cli write command. All actions must go into the pending JSON; the orchestrator
     will present them to the user for approval via apply/skip.
   - For §1b Fixable=Yes: invoke `/bug-start {id} --triage-mode`
     synchronously in this subagent. Parallel subagents make wall-clock
     cost ≈ `max(per-bug)` not `sum`, so total /triage time stays
     bounded. Triage mode runs in ~5 min and produces a shallow but
     useful investigation (frontmatter + Summary + Findings + Proposed
     Solution + Notes); see the `/bug-start` skill → Invocation Modes.

     The §1b decision itself is the only gate. Trust /triage's existing
     "Fixable=Yes: enough diagnostic data exists to start analysis"
     judgment — DO NOT require a specific artifact type beyond that.
     Sufficient evidence for §1b includes any of: media-preset profile
     analysis, media log with NS_ERROR / decoder signal, crash ID with
     media stack frame, reporter-identified root cause with source code
     citations, codec / configuration identification with a clear
     cross-browser failure pattern, existing current investigation file,
     and other forms of analyzable evidence. Step 2c's media-vs-generic
     profile check is the safeguard that prevents a non-media profile
     from masquerading as a media profile — that's the only artifact-type
     rule. /bug-start's own skip-if-current rule makes spurious dispatches
     cheap (they exit silently and log `outcome: skipped`).
   - **Read-only analysis IS allowed** — you MUST run profiler-cli for any Firefox Profiler
     links in the bug. Do NOT skip profile analysis even if the reporter says the issue is
     resolved. Use: `profiler-cli <url> --calltree 20`
   ```

**Parallelism cap**: dispatch at most **4 subagents concurrently**, not
all at once. Bugzilla / searchfox / profiler.firefox.com don't love
10 simultaneous callers from one IP, and the orchestrator itself needs
context-window headroom. As each subagent finishes, start the next.

3. **Wait** for all background agents to notify completion before merging.

4. **Merge results** after all agents finish:

   ```bash
   # Merge triage-log tmp files into triage-log.json (the dashboard reads this)
   python3 - <<'EOF'
   import json, glob, os
   log_path = os.path.expanduser('~/firefox-triage/triage-log.json')
   entries = json.load(open(log_path)) if os.path.exists(log_path) else []
   for f in sorted(glob.glob(os.path.expanduser('~/firefox-triage/triage-log-tmp-*.json'))):
       entries.extend(json.load(open(f)))
       os.remove(f)
   json.dump(entries, open(log_path, 'w'), indent=2)
   print(f"Merged {len(entries)} total entries")
   EOF

   # Run deferred watch-add calls
   for f in ~/firefox-triage/watch-tmp-*.json 2>/dev/null; do
     [ -f "$f" ] || continue
     bug_id=$(python3 -c "import json; d=json.load(open('$f')); print(d['bug_id'])")
     title=$(python3 -c "import json; d=json.load(open('$f')); print(d['title'])")
     ni_args=$(python3 -c "import json; d=json.load(open('$f')); print(' '.join(['--ni '+e for e in d['ni_targets']]))")
     bugzilla-cli watch-add "$bug_id" --title "$title" $ni_args
     rm "$f"
   done
   ```

   Investigation files written by the dispatched `/bug-start --triage-mode`
   subagents stay **local** in `$FX_BUG_INVESTIGATION_DIR/`; the dashboard reads
   and serves them from there (`/investigation/<id>`) — no push to any remote
   repo is needed.

5. **Add new triage patterns to the wiki** if any agent's result revealed a non-obvious pattern worth remembering. Use `/firefox-wiki:add` — never write to files directly.

6. **Print a summary table** of all decisions:

   ```
   ─── Triage session complete ──────────────────────────────────
   Bug       Decision      Reason
   -------   -----------   ----------------------------------------
   2027038   ni_sent       Missing STR + media log
   2028507   triaged       Root cause found → /bug-start invoked
   ─────────────────────────────────────────────────────────────
   ```

7. **Open the triage dashboard** to review the drafts: invoke
   **`/triage-dashboard`**. On the *first* run it asks to install the dashboard
   (a one-time venv + pip bootstrap); afterwards it just serves the board at
   `http://127.0.0.1:8765/`. End your report with that URL so the user can review
   and apply the pending drafts. (Skip silently if the user declines the install
   — the drafts are already written to `$TRIAGE_DIR`.)

---

## Pre-flight skip check

Before running the 6-step workflow, check five conditions and skip immediately if any is true:

**1. Out-of-scope component:**
Bug's `component` field is not in the configured component set (resolved
`$TRIAGE_COMPONENTS`; see Triage scope — components and Setup check).
→ Print: `Skipping bug {id} — component "{component}" is out of scope.` Move to next.

**2. Meta bug:**
Skip if any of the following:
- Bug has the `meta` keyword in its `keywords` field
- Bug title contains `[meta]` (case-insensitive)
- Bug title contains the word `meta` adjacent to `bug` (e.g. "meta bug", "meta-bug")

→ Print: `Skipping bug {id} — meta bug.` Move to next.

**3. Filed by a non-QA Mozilla employee:**
Bug's `creator` field ends with `@mozilla.com` AND the creator is not QA.
Developer-filed bugs don't need triage; QA-filed bugs do.

Detect QA by any of these signals (OR logic):
- `cf_qa_whiteboard` field is non-empty
- `creator_detail.real_name` contains any of: `QA`, `Quality`, `Test Engineering`, `Testing`
- `/firefox-wiki:lookup qa mozilla accounts {email}` returns a match

If Mozilla employee AND not QA → Print: `Skipping bug {id} — filed by Mozilla employee ({creator}).` Move to next.
If Mozilla employee AND QA → continue with the 6-step workflow.

When a Mozilla employee is confirmed QA via wiki lookup (not by name/whiteboard),
record them: `/firefox-wiki:add` to `triage/qa-mozilla-accounts.md` with their email, name, and date confirmed.

**4. Already resolved/closed:**
Bug's `status` is `RESOLVED` or `VERIFIED` (any resolution — FIXED, DUPLICATE,
WONTFIX, INVALID, INCOMPLETE, WORKSFORME).
→ Print: `Skipping bug {id} — already {status} {resolution}.` Move to next. A
closed bug does not need triage and must never become a pending draft.

This also applies to a bug we **already** drafted: if it gets resolved upstream
before you apply (e.g. the assignee lands a patch), the next `/triage` must
**drop the stale pending draft** — never keep showing a fixed bug in the
dashboard. (Surfaced by bug 2044408: RESOLVED FIXED while a §1b draft was still
pending.)

**5. Already awaiting a reply (on the NI watch list):**
The bug is already in the NI watch store (`$TRIAGE_DIR/ni-watch.json`, a JSON
object keyed by bug id) with a needinfo we set, and the party we need has **not
substantively replied since**. This is the gate that makes "are we still
awaiting?" (see the watch-poll section) apply to bugs reached via `fetch`, not
just those surfaced by `watch-poll`: a recently-filed bug we already needinfo'd
in a prior round *also* re-appears in the 14-day `fetch`, and without this check
the fetch path re-drafts a duplicate §1a needs-info for a bug we are already
waiting on (surfaced by bug 2043826 — NI set 2026-06-02, re-drafted two days
later).

Check: look up `<id>` in `ni-watch.json`. If present, read its `ni_set_date` /
`ni_targets`, then determine — using the **same substantive-vs-non-substantive
test as the watch-poll handling** — whether an `ni_targets` party has
substantively replied after `ni_set_date` and whether the NI flag is still
active on that party.
- **Still awaiting** (NI flag still active on the needed party, no substantive
  reply since `ni_set_date`, and not yet stale — set < 14 days ago): →
  Print: `Skipping bug {id} — already awaiting reply (NI on {target} since
  {date}).` Do NOT create a §1a needs-info draft (it would re-ping a reporter we
  already asked). **And if a pending §1a draft already exists for this bug**
  (e.g. written by a prior run's fetch path before this guard), **drop it**
  (`rm $TRIAGE_DIR/pending/bug-{id}.json`) so it leaves NeedInfos and the bug
  shows correctly under Awaiting. Move to next.
- **Not awaiting anymore** — a substantive reply arrived after `ni_set_date`, the
  NI was cleared, or the NI is stale (≥ 14 days): do NOT skip. Fall through to the
  6-step workflow (this is the legitimate `replied` / `ni_cleared` re-triage or
  `stale` → INCOMPLETE path).

This check reads `ni-watch.json` directly; it does **not** call `watch-poll`, so
it is also safe in single-bug mode.

---

## For each bug: 6-step workflow

### Step 1 — Fetch full bug + comments

```bash
bmo-to-md <id>
```

**Stale pending draft check:** before running Steps 2–6, check whether a pending file already exists:

```bash
cat ~/firefox-triage/pending/bug-<id>.json 2>/dev/null
```

If a pending file exists, compare its `created_at` against the bug's `last_change_time` from the fetch output:

- **No new comments** (`last_change_time <= created_at`): re-show the existing draft as-is. Do not re-run Steps 2–6.
- **New comments arrived** (`last_change_time > created_at`): the reporter (or someone else) has posted since the draft was written. **Discard the stale draft** and re-run Steps 2–6 from scratch on the full updated bug.

When re-running after new comments, pay special attention in Step 2c to any diagnostic artifacts in the new comments (profiler links, media logs, crash IDs, about:support). If those artifacts are sufficient to understand the root cause, go directly to §1b — which means invoking `/bug-start {id}` — rather than sending another §1a NI request.

**§1b backfill carve-out** — Even when "No new comments" applies and Steps 2–6
are skipped, **still dispatch `/bug-start {id} --triage-mode` at the end of
this subagent IF**:
1. The existing draft classifies as §1b (severity/priority set in the
   pending JSON), AND
2. No current investigation file exists at
   `$FX_BUG_INVESTIGATION_DIR/bug-{id}-investigation.md` (or it's stale
   per `/bug-start`'s skip-if-current rule).

`/bug-start`'s own skip-if-current rule handles the no-op case
efficiently: if the investigation already exists and is current, the
dispatched subagent exits silently and logs `outcome: "skipped"`. So this
carve-out is safe to apply unconditionally to §1b drafts — the cost is
one quick subagent that exits in seconds when the investigation already
exists.

This carve-out backfills investigations on §1b drafts that were created
before the queue-at-draft-time mechanism existed. Without it, those
drafts would never get `/bug-start` dispatched on a re-/triage run —
the Step 2–6 skip would also skip the dispatch.

### Step 2 — Extract what is already known

Before deciding what to ask, explicitly inventory what is present:

```
Already present:
  ✓ Platform: Windows 11
  ✓ Firefox version: 136.0
  ✓ STR: [clear steps in description]
  ✗ about:support: not provided
  ✗ Media sample or URL: not provided
  ✗ Codec/container: not specified
```

**Always do this step.** Never ask for information that is already in the bug.

**Assume Firefox always.** Bugzilla is a Firefox bug tracker. If the User Agent string shows
Chrome or another browser, treat it as a formatting artifact (reporter filed from a different
profile or copied the wrong UA). Never ask the reporter to confirm whether they are using Firefox
— assume they are and proceed with the triage.

#### Step 2b — Analyze about:support (if present)

If about:support is included in any comment (look for "Application Basics" or "Important Modified Preferences"), extract and analyze the following sections. All findings feed directly into Steps 3–5.

**Re-run Step 2b on every new reporter response** that contains about:support — prefs and state may have changed.

---

**1. Important Modified Preferences**

Find `media.*` prefs that are non-default. Flag any that could explain or contribute to the issue.

Key prefs to watch and their defaults:

| Pref | Default | Risk if changed |
|---|---|---|
| `media.hardware-video-decoding.enabled` | `true` | **Critical** — disabling removes HW decode path entirely |
| `media.ffmpeg.disable-software-fallback` | `false` | **High** — combined with disabled HW decode, leaves no working decode path |
| `media.ffmpeg.enabled` | `false` on macOS/Win, `true` on Linux | Medium — enabling on macOS/Win activates non-default decode path |
| `media.ffvpx-hw.enabled` | `false` | Medium — experimental HW path via ffvpx; only AV1/VPX on macOS/Win (see [[triage/ffvpx-hw-decode-codec-support]]) |
| `media.mediasource.experimental.enabled` | `false` | Medium — experimental MSE features |
| `media.autoplay.default` | `1` | Low — autoplay policy, unlikely to cause failure |

If high-risk prefs are found, that becomes the primary ask in §1a: reset all `media.*` prefs first, then reproduce and capture a media log.

**Important:** after resetting any HW decode prefs, the reporter must **fully close all Firefox instances and restart** before testing — the pref change does not take effect until then. Always include this in the NI comment.

---

**2. Decision Log**

Look for the `HARDWARE_VIDEO_DECODING` and `HARDWARE_VIDEO_ENCODING` entries. They show whether HW decoding is available, and if not, *why* (blocklisted, pref-disabled, driver issue, etc.).

```
HARDWARE_VIDEO_DECODING:
  default: available,
  user: disabled, User disabled via media.hardware-video-decoding.enabled pref
```

Note the failure code — it distinguishes user-disabled from driver blocklist from capability missing.

---

**3. Media — Codec Support Information**

Shows per-codec decode/encode support. Check whether the relevant codec (H.264, AV1, VP9, HEVC, etc.) shows SW and/or HW support. If a codec shows no support at all, the issue may be a missing decoder rather than a configuration problem.

---

**4. Media — Content Decryption Modules (CDM) Information**

Shows installed CDMs (Widevine, OpenH264, WMF CDM / PlayReady). Relevant for EME/DRM bugs. Check if the expected CDM is present and its version. Mostly useful for `Audio/Video: GMP` bugs.

---

**5. Graphics section**

Check:
- **GPU info** — GPU vendor/model, driver version (relevant for HW decode failures)
- **WebRender / compositor** — software vs hardware compositing (can affect playback rendering)
- **Feature flags** — any features listed as BLOCKED or DISABLED that relate to video

Summarize findings as part of the inventory:
```
  ✓ HW decoding:   user-disabled via pref (HIGH RISK)
  ✓ H.264 support: SW available, HW unavailable (blocked)
  ✓ CDM:           Widevine 4.10.x present
  ✓ GPU:           Apple M2, driver N/A
```

#### Step 2c — Analyze diagnostic artifacts (if present)

**Before analyzing artifacts, look up the Firefox Knowledge Wiki for relevant components.**
The wiki (`~/firefox-wiki/components/`) contains known behaviors, quirks, and root
causes for components like `D3D11DXVA2Manager`, `WMFVideoMFTManager`, `MediaCapabilities`,
`MDSM`, etc. Run:
```
/firefox-wiki:lookup <ComponentName>
```
Known facts from the wiki can identify the root cause without reading code. Only read
source code if the wiki doesn't cover the observed symptom.

When the bug or a reporter reply contains links or attachments for profiler captures,
media logs, or crash IDs, **attempt analysis before proceeding to Step 5**. Do not
skip this and assume more data is needed — the artifacts may already be sufficient
for §1b.

**⚠️ Triage scope limit — do NOT inline-investigate code during triage:**
Triage's job is to identify *what kind of problem this is* and whether enough data
exists to start a fix. When you reach §1b (root cause identifiable), **stop** — do
not read source files, trace call stacks, or reason about fix approaches. That work
belongs in `/bug-start`. The correct flow is:
1. Profile/log analysis → identify symptom pattern (e.g. "DXVA failure per scroll")
2. Wiki lookup → check if root cause is already known
3. If yes: root cause confirmed → §1b Fixable=Yes → hand off to `/bug-start`
4. If no: symptom pattern identified but root cause unclear → still §1b if data is
   sufficient to investigate, or §1a if more data needed

The anti-pattern to avoid: seeing a `DXVA failure:` in the profile → reading
`DXVA2Manager.cpp` → checking `sDXVAVideosCount` → checking prefs → reasoning
about capability API mismatches — all during triage. This is `/bug-start` work.

**Firefox Profiler links (`share.firefox.dev/*` or `profiler.firefox.com/public/*`):**
- Do NOT use WebFetch — these are JavaScript SPAs; WebFetch returns only the CSS shell.
- Do NOT run `profiler-cli` directly — **invoke `/analyze-profile <url>` instead**.
  That skill runs the full standard query set, checks all media threads, pattern-matches
  against known signatures, and produces a structured findings report.
- Record the findings report in the inventory. Use the "Sufficient for §1b?" field
  from the report to decide §1a vs §1b — do not make that judgment independently.

**Media profile vs generic profile — REQUIRED check before §1b:**
A profile link by itself does NOT prove a media bug is investigatable. The
capture must be a **media-preset profile** (recorded with the "Media" preset
in Firefox Profiler), so it includes the media-specific threads:
`MediaDecoderStateMachine`, `MediaSupervisor`, `MediaPDecoder`, `AudioSink`,
`AudioIPC`, `cubeb`, plus markers like `DXVA` and `NS_ERROR_DOM_MEDIA_*`.
A generic CPU/JS/networking profile will surface none of this signal and
**cannot support a §1b classification** for a media bug — Firefox A/V triage
covers media bugs exclusively.

When `/analyze-profile <url>` runs, scan its output for the media-thread
list. If **none** of the expected media threads (MDSM, MediaSupervisor,
MediaPDecoder, AudioSink, AudioIPC, cubeb) appear, the profile is NOT a
media profile. In that case:
- Record `profile (non-media)` in `inventory_present`.
- Add `media profile` to `inventory_missing`.
- **Do NOT classify as §1b** on the strength of the link alone — fall back
  to §1a with an NI asking the reporter to capture a new profile using the
  "Media" preset (see the NI templates). The existing non-media profile is
  fine to retain for context but it doesn't unlock §1b.

If at least one expected media thread appears in the report, record
`profile (media)` in `inventory_present` and §1b remains open as documented.

This rule exists because a previous bug (2040168) was misclassified §1b on
the strength of a non-media profile alone — the inventory check passed
("profiler link") but the artifact lacked the threads needed to actually
investigate the issue. Inventory items now carry the media-vs-non-media
distinction so this can't recur.

**Media logs attached inline in comments:**
- If log content appears directly in a comment (JSON or text), extract and scan it:
  look for `NS_ERROR_*` codes, decoder selection (`AppleMedia`, `ffvpx`, `VPX`),
  MSE state transitions, network stalls, `MediaDecoderStateMachine` errors.
- Summarize findings in the inventory before deciding §1a vs §1b.

**Media logs emailed to media-alerts@mozilla.com:**
- Record: `✓ Log sent via email — not accessible to triage bot`. Treat as present but
  unanalyzed. Do not ask the reporter to re-send.

**Crash IDs (`bp-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX`):**
- Fetch via WebFetch: `https://crash-stats.mozilla.org/api/ProcessedCrash/?crash_id={id}`
- Extract: crash signature, OS, module/frame that crashed, any media stack frames.
- A crash ID with a clear media signature is sufficient for §1b.

**When analyzing a profile, always check ALL media-related threads**, not just `MediaDecoderStateMachine #1`. Run:
```bash
profiler-cli <url> --log-markers "DXVA"
profiler-cli <url> --log-markers "NS_ERROR"
```
Check `MediaSupervisor #N`, `MediaPDecoder #N`, and `GeckoMain` threads in addition to MDSM. Missing a thread means missing the root cause.

**HW decode failure pattern — always investigate capability API accuracy:**

When the profile contains repeated `DXVA failure:` or `NS_ERROR_DOM_MEDIA_*` entries, ask:
1. **Why does it fail each time?** Common causes:
   - DXVA slot exhaustion: `DXVA failure: D3D11: Too many DXVA videos playing` — Firefox caps concurrent DXVA decoders at `media.wmf.dxva.max-videos` (default 8). Feed-style sites (douyin, TikTok, Instagram) keep many videos alive simultaneously and hit this limit.
   - `CanUseDXVA()` returning false for this specific video's parameters (resolution, color depth, pixel format)
   - D3D11 device creation failure (driver issue, GPU reset)
2. **Does the capability API accurately reflect runtime availability?** `WMFDecoderModule::Supports()` (used by `MediaCapabilities.decodingInfo()`) checks only process-level `sDXVAEnabled` and MFT type presence — it does **not** check the current DXVA slot count. So Firefox can report a codec as `HardwareDecode` supported even when new decoders will immediately fail at runtime.
3. **Does the failing codec have a software fallback?** In WMF: H.264 has SW fallback; HEVC, VP9, AV1, VP8 do **not** (`WMFVideoMFTManager.cpp` returns `NS_ERROR_DOM_MEDIA_FATAL_ERR` if HW fails for these). A capability mismatch is especially impactful for no-fallback codecs — the site gets `NS_ERROR_DOM_MEDIA_METADATA_ERR` and must re-probe with a different codec.

When all three conditions are present (repeated HW failure + no-SW-fallback codec + capability API reports supported), this is §1b — root cause is identified, two separate bugs:
- The DXVA limit or HW failure root cause
- The capability API not reflecting runtime HW availability

**Decision rule:** after Step 2c, update the inventory with artifact findings and use
them — not just checklist presence — to determine §1a vs §1b in Step 6. A bug with
a *media* profiler link (per the media-vs-generic check above) + clean about:support
+ repro URL is likely §1b even if the log content itself is unanalyzable by the
triage bot. A *non-media* profiler link does NOT unlock §1b on its own — the bug
needs a media profile (or another equally-informative media artifact: media log with
NS_ERROR/decoder signal, or a crash ID with a media stack frame) before §1b applies.

### Step 3 — Classify bug type

| Type | Indicators | Typical component |
|---|---|---|
| Crash | "crash", crash-stats URL, crash ID in title/comments | Any |
| Regression | "used to work", "stopped working", "broke in", version comparison | Any |
| Playback failure | video/audio element not playing, codec/container mentioned | Audio/Video: Playback |
| Recording | getUserMedia, MediaRecorder, microphone, camera | Audio/Video: Recording |
| Web Audio | AudioContext, AudioNode, Web Audio API | Web Audio |
| Web Codecs | VideoDecoder, VideoEncoder, AudioDecoder, AudioEncoder | Audio/Video: Web Codecs |
| Performance / audio quality | slow, high CPU, dropped frames, buffering, audio glitch | Audio/Video: Playback, cubeb, MediaStreamGraph |
| GMP / EME | CDM, Widevine, PlayReady, EME, encrypted media | Audio/Video: GMP |
| Build / infra | compile error, test failure, CI | Any |

When a bug is a **Regression** (it used to work, or you identify a regressor),
record the signal in the draft so it's tagged on Bugzilla and surfaces in the
dashboard's `regression` rail tag: add `keywords_add: ["regression"]` and/or a
`see_also` entry labelled `regressor`. Do not leave a known regression with no
regression signal in its draft.

**When the regressor bug is known** (a bisection result, a "regressed by bug N"
note, or your own Step 4 root-cause identifying the causing change), also set
`regressed_by_add: [<regressor_bug_id>]`. This populates Bugzilla's structured
`regressed_by` relation (not just the `regression` keyword) via
`bugzilla-cli set-fields --regressed-by-add`, which apply runs automatically. A
`see_also` regressor label is the soft signal; `regressed_by_add` is the
authoritative relation — set it whenever you actually know the regressor, never
guess an ID.

### Step 4 — Check for duplicates and meta bug match

**4a — Duplicate search:** Search for similar bugs in the in-scope components
using keywords from title/description. Also check the dependency list of any
matching meta bug (Step 4b).

If a likely duplicate is found → propose marking as duplicate (§1c).

**4b — Meta bug match:** Check against the known meta bugs list below. If a
match is found, record the meta bug number to add as a blocker.

### Step 5 — Determine info gaps

Cross-reference extracted inventory against required info per bug type. Only flag
items that are genuinely absent:

| Bug type | Required info |
|---|---|
| Crash | crash-stats URL or crash ID, about:support, STR |
| Regression | first broken / last good build (suggest mozregression), STR |
| Playback failure | media URL or sample file, codec/container, about:support, platform |
| Recording | device info, getUserMedia constraints, repro page or snippet |
| Web Audio | minimal reproducible JS snippet, AudioContext config, about:support |
| Web Codecs | minimal reproducible JS snippet, codec config, about:support |
| Performance / audio quality | `about:logging` capture with media preset (see Media Log Instructions), platform, STR |
| GMP / EME | key system (Widevine/PlayReady), platform, about:support |

### Step 6 — Branch

- **§1a** — info gap detected → needs info path
- **§1b** — enough info → triage path
- **§1c** — duplicate / invalid / not-our-bug → close/reassign path

### Dedup check before building any ACTIONS block

Before listing any action, check the current bug state (from `bugzilla-cli get`) and
**omit any action whose target value is already set**:

| Attribute | Skip if… |
|---|---|
| `priority` | already set to the target value (not `--`) |
| `severity` | already set to the target value (not `--`) |
| `cc_add` | email already in the `cc` list |
| `blocks_add` | bug number already in the `blocks` list |
| `component` | already the correct component |
| `keywords_add` | keyword already in the `keywords` list |
| `needinfo` | NI flag already set on that email |

Never overwrite a P/S that was already set by a developer — only set P/S when the
current value is `--`. If P/S is already set to a different value and you disagree,
add a note in the comment explaining your assessment instead.

---

## §1a — Needs Info Path

P/S is **not changed** when sending NI.

Draft a comment asking only for items identified as missing in Step 5. Always include:
- The specific missing items
- `about:support` if not already provided
- Media log instructions (Loom link) if the issue is audio/video/performance-related
- mozregression hint if it is a regression

**Standard diagnostic questions to consider** (include only what is relevant):

| Question | When to ask |
|---|---|
| Does this happen in Private Browsing mode? | Any playback/recording issue — rules out extensions |
| Does this happen on all videos, or only certain ones? | Playback failures |
| Does this happen on a specific codec only? (H.264, H.265, AV1, VP9) | Playback failures with codec hint |
| Can you share a public/open link to reproduce? | When reported URL requires login |
| If the content is private, you can email it to media-alerts@mozilla.com — please set needinfo on the triage owner | When no public repro is possible |

**NI targets:** reporter by default; add others who confirmed reproduction if mentioned in comments.

**Email resolution:** BMO's REST API requires the full email address for needinfo flags — the `:alias` shorthand (e.g. `:sotaro`) only works in comment text and the web UI. If you only know someone's alias, look up their email in a recent bug comment or ask the user. Known aliases: `:sotaro` → `sotaro.ikeda.g@gmail.com`.

Write `~/firefox-triage/pending/bug-{id}.json` — including the `bug_context` block populated from Steps 2/2b/2c (see Pending JSON Format below). Then show:

```
─── DRAFT: Bug {id} — {title} ───────────────────────────────
[INTERNAL — not posted]
Already in bug:
  ✓ {item}: {value}
  ✗ {item}: missing → will ask

COMMENT (posted to Bugzilla):
[If about:support analysis found significant findings:]
**Analysis**

{1–3 sentences summarizing relevant findings from about:support, e.g. non-default
prefs detected, HW decode status, codec support gaps. Write for both the reporter
and developers reading later. Do NOT reproduce the ✓/✗ inventory here.}

**Next Steps**

{Ask only for genuinely missing items. One bullet per item. For audio/video/performance
bugs the media-log capture is item 1 by default (see Media Log Instructions) — UNLESS
high-risk prefs were found, in which case lead with the reset + restart and make the
capture the next item.}

[If no about:support or no significant findings, omit the Analysis section and lead
directly with a brief acknowledgement + the Next Steps ask.]

[media-log capture block — the FIRST Next Steps item for A/V/perf issues (or right after
the pref-reset step when high-risk prefs were found)]
[mozregression block if regression]

NI TARGETS: {email1} (reporter)[, {email2}]
META BUG BLOCKER: [bug {n} — {alias}] or [none]
P/S: unchanged

ACTIONS ON APPROVAL (apply {id}):
  POST comment via bot account                      → bugzilla-cli post-comment {id} "..."
  [SET needinfo?({email1})]  (skip if NI already set) → bugzilla-cli set-ni {id} {email1}
  [SET blocks: bug {n}]      (skip if already blocks)  → bugzilla-cli set-fields {id} --blocks-add {n}
  [Owner CC / NI: off by default — toggle "CC me"/"NI me" in the dashboard to add $TRIAGE_OWNER]

Type "apply {id}" to post, "skip {id}" to skip.
─────────────────────────────────────────────────────────────
```

The ✓/✗ inventory is internal triage bookkeeping shown in the terminal only — it
is **never included in the posted comment**. The comment should read as a natural,
human-readable response, not as a checklist.

**Comment voice — the triage account is a bot, not a person. Write advisory, not
volitional.** Never use first-person preference/intention phrasing in a posted
comment: avoid "I'd like to…", "I'll take a look", "I'll start…", "I want to…",
"I personally…", "let me…". Use neutral or suggestion phrasing instead:
"I'd suggest…", "Suggest…", "Recommend…", "The next step is…", "This looks
like…", "We can…". This applies to **every** posted comment.

**Keep the findings in the comment; make only the Next Steps reporter-clear.**
Do NOT strip the root-cause analysis/findings out of the posted comment to
"simplify" it — the Analysis (including code-level root cause, citations, and
the planned fix direction) is valuable on the bug for developers and shows the
reporter the issue is understood, so keep it. What must be plain and actionable
is the **Next Steps** section the reporter acts on: a clear, numbered workaround
or a concrete "what to capture", not engineering jargon. In short: full Analysis
+ developer detail stays; only the reporter's Next Steps get simplified.

**Verify a fix attribution before stating it.** Before telling a reporter (or
writing in `ai_reasoning`) that a specific bug/change fixed an issue, check its
landing/build date against the build that still reproduced — *a change already
present in the reproducing build cannot be the fix.* If the issue is reported
fixed but no fixing change landed in the regression window, say the fix is
unconfirmed and recommend `mozregression`; for site-specific issues (e.g.
YouTube) also consider a server-side change.

After `watch-poll` returns `replied` or `ni_cleared`, first decide whether the
change is **substantive** before re-triaging — a reply does not always change the
bug's situation:

- **Non-substantive → keep it in Awaiting.** `replied` fires when *any* watched
  person comments, but a comment that doesn't advance the bug — a watched
  developer merely re-asking the reporter for the same data, a bot/automation
  note, or any comment that is not the awaited answer or a new analyzable
  artifact — leaves the bug **still waiting**. Do NOT pull it into a §-tab:
  keep it on the watch list (still NI'd on whoever you're waiting on, typically
  the reporter) and write **no** pending draft. (Example: a co-owner like Sotaro
  posting "reporter, can you attach about:support?" is the watched bug *still
  awaiting the reporter*, not a reply to act on.)
- **Substantive → re-enter the full triage flow from Step 1.** The reporter
  provided the awaited data, a new analyzable artifact appeared, or the NI was
  genuinely answered. **Step 2c is critical on re-triage**: the reply almost
  always contains new diagnostic artifacts (profiler links, log files, crash IDs,
  updated about:support). Analyze them before deciding §1a vs §1b — do not fall
  back to §1a purely because artifacts are unanalyzable. A profiler link + clean
  about:support + repro URL is typically sufficient for §1b even if the log
  content cannot be read by the triage bot.

**When a bug moves OUT of Awaiting into a §-tab, set a `change_note`.** Write a
one-line `bug_context.change_note` summarizing what changed since it was last
awaiting (e.g. "Reporter attached a media log → re-triaged §1b" or "NI answered
off-channel; closing INCOMPLETE"). The dashboard renders it as a row so the move
from Awaiting is self-explanatory. Leave `change_note` empty when the bug was not
previously in Awaiting (a fresh bug carries no change note).

If the response now contains enough information to proceed to investigation
(re-triage result is §1b, not another §1a), set a needinfo on the bot account
itself (`$BOT_EMAIL`) as a signal that the bug is ready for investigation. This
surfaces the bug in the bot's NI queue so it is not lost.

`stale` bugs (14 days, no reply) → propose INCOMPLETE via §1c.
`auto_removed` and `inaccessible` → log, no Bugzilla action.

---

## §1b — Triage Path

Apply the P/S standard. Check meta bug blocking.

**If Fixable = Yes:**
1. Invoke `/bug-start {id}` first — do NOT set any fields or post any comment before it completes.
2. After `/bug-start` completes, read the investigation file and determine the outcome:
   - **Root cause found** → draft a comment summarising findings + next steps, then include P/S and the meta bug blocker in the same `apply` (one atomic action). Do **not** auto-CC or auto-NI the triage owner — that's the owner's per-draft choice via the dashboard's "CC me" / "NI me" checkboxes (default off); a checked "NI me" is the "ready for implementation, owner's attention" signal. **Never include a link to the local investigation file** (`$FX_BUG_INVESTIGATION_DIR/`) in the Bugzilla comment — it is an internal working document, not a public artifact.
   - **Investigation reveals missing info** → fall back to §1a; draft NI comment asking for the specific missing data, with P/S in the same `apply`.
3. **Never set P/S or meta bug blocker as standalone operations** — always bundle them with a comment so Bugzilla shows a coherent update.

**Asking the reporter for anything = a reporter needinfo.** Even on a §1b draft
(P/S set, root cause investigatable), if the comment requests *any* artifact or
action from the reporter — a media-preset profile, a media log, about:support, a
sample, STR, or a workaround-test result — that is a reporter action: add the
reporter (`bug_context.reporter_email`) to `ni_targets`, and never phrase it as
"no action needed from you". The reporter NI is independent of the owner's "CC
me"/"NI me" choice above. A profile/log request drafted with no NI silently
strips the tracking (the bug never enters Awaiting) — surfaced by bug 2044925,
whose §1b draft said "No action needed from you" while asking for a profile. If
you genuinely need nothing from the reporter, then don't ask — omit the request
entirely rather than leaving a dangling, untracked one.

**If Fixable = No (root cause unknown, more data needed):** skip investigation, go directly to §1a.

### Priority & Severity Standard

**Severity:**

| Severity | Definition | Examples |
|---|---|---|
| S1 | Complete loss of core media functionality; crash; data corruption; security issue | Browser crashes on media playback; camera feed corrupts recorded file |
| S2 | Major feature broken with no workaround; regression from a previous release | Video playback completely broken on a common codec; getUserMedia returns error on all devices after an update |
| S3 | Feature degraded but a workaround exists; regression in Nightly/Beta not yet in release | Playback fails for a specific rare container; audio desync on long files |
| S4 | Minor / cosmetic / low-impact; spec compliance gap with no user-visible breakage; enhancement | Poster frame not shown for 1 frame before play; minor wording in error message |

**Priority:**

| Priority | Definition | Examples |
|---|---|---|
| P1 | Must fix before next release; active regression or crash affecting significant users | S1 bug confirmed on release; regression from a landed patch blocking uplift |
| P2 | Should fix in current cycle; confirmed reproducible bug with known user impact | Playback failure reproducible with clear STR; crash reproducible reliably |
| P3 | Fix when possible; low user impact or hard-to-reproduce edge case | Obscure codec variant; single-reporter issue with no duplicates |
| P4 | Tracking / future work; spec gaps, enhancements, cleanup | Implementing a new codec variant; improving error messaging |

**Decision matrix:**

| Situation | Severity | Priority |
|---|---|---|
| Crash with crash-stats ID, multiple reporters | S1 | P1 |
| Playback regression introduced in current Nightly | S2 | P1 |
| Playback broken on a specific site, no workaround | S2 | P2 |
| Playback broken for a codec/container, another format works | S3 | P2 |
| Recording works but quality is degraded | S3 | P3 |
| CI / test-infra crash (e.g. xpcshell), no user-facing playback impact | S3 | P2 |
| Feature request / enhancement | S4 | P4 |

Rate severity by **user-facing impact, not crash frequency**. A crash that
only happens in CI / test infrastructure (e.g. an xpcshell `plugin-container`
SIGABRT), however frequent, is **S3** — S2 is reserved for serious user-facing
breakage. Do not let a high CI failure count inflate it to S2/P1.

### Fixability assessment

| Outcome | Meaning | Next action |
|---|---|---|
| Fixable | Root cause is clear or investigatable (enough diagnostic data exists to start analysis) | Show ASSESSMENT + ACTIONS ON APPROVAL; wait for `apply {id}`, then invoke `/bug-start {id}` |
| Root cause unknown, more data needed | Diagnostic info still missing after triage | Back to §1a — NI for specific diagnostic data |
| Root cause unknown, no path forward | All info gathered, still can't locate problem | §1c — add `stalled` keyword + comment |
| Works as intended | Behavior matches spec or design intent | §1c — INVALID/WONTFIX |
| Not our bug | Wrong component, OS/driver, third-party | §1c — component change or INCOMPLETE |
| Already fixed | Matching fix found in recent commits or another bug | §1c — FIXED or DUPLICATE |

Show assessment for all §1b cases. **Never execute Bugzilla writes before user approval** — always
write `~/firefox-triage/pending/bug-{id}.json` — including the `bug_context` block populated from Steps 2/2b/2c — and show the draft, then wait for `apply {id}`:

```
─── ASSESSMENT: Bug {id} — {title} ──────────────────────────
  Severity: S{n} — {one-line rationale}
  Priority: P{n} — {one-line rationale}
  Meta bug blocker: bug {n} ({alias}) [or none]
  Fixable: [Yes — {reason} / No — {reason}]

ACTIONS ON APPROVAL (apply {id}):
  [SET severity → S{n}]  (skip if already S{n})           → bugzilla-cli set-fields {id} --severity S{n}
  [SET priority → P{n}]  (skip if already P{n})           → bugzilla-cli set-fields {id} --priority P{n}
  [SET blocks: bug {n}]  (skip if already blocks)         → bugzilla-cli set-fields {id} --blocks-add {n}
  [POST comment]                                          → bugzilla-cli post-comment {id} "..."
  [SET needinfo?({reporter})] (§1a only)                  → bugzilla-cli set-ni {id} {reporter}
  [Owner CC / NI: off by default — toggle "CC me"/"NI me" in the dashboard to add $TRIAGE_OWNER to cc_add/ni_targets]
  [Fixable=Yes: /bug-start already run before this apply]

Type "apply {id}" to execute, "skip {id}" to skip.
─────────────────────────────────────────────────────────────
```

For Fixable = Yes: after `apply {id}` executes the field changes, invoke `/bug-start {id}` automatically.

---

## §1c — Close / Reassign / Duplicate

| Case | Proposed action | CLI command |
|---|---|---|
| Duplicate of bug {n} | DUPLICATE → bug {n}, add comment explaining the link | `bugzilla-cli set-fields {id} --status RESOLVED --resolution DUPLICATE --dupe-of {n}` |
| Works as intended | INVALID + comment explaining design intent / spec reference | `bugzilla-cli set-fields {id} --status RESOLVED --resolution INVALID` |
| Not reproducible / insufficient info | INCOMPLETE + comment | `bugzilla-cli set-fields {id} --status RESOLVED --resolution INCOMPLETE` |
| Already fixed | FIXED or DUPLICATE of fixing bug | `bugzilla-cli set-fields {id} --status RESOLVED --resolution FIXED` |
| No path forward | Add `stalled` keyword + comment | `bugzilla-cli set-fields {id} --keywords-add stalled` |
| Wrong component | Reassign to correct component + comment | `bugzilla-cli set-fields {id} --product "{product}" --component "{component}"` |

For a wrong-component reassignment, set the draft's `product`/`component` to the
**TARGET destination** (where the bug should go) — **never** the bug's *current*
component. Setting the current component is a no-op move and renders a confusing
"move to <current component>" in the dashboard's will-apply diff. Keep the bug's
current component in `bug_context.bug_component` (for the card-head); put the
target in the top-level `product`/`component`. (Surfaced by bug 2043943: a route-
to-Graphics draft mistakenly set `component` to the current `Audio/Video:
Playback`, so will-apply showed a move back to A/V.)

### ⚠️ WORKSFORME — never use prematurely

**WORKSFORME is almost never the right resolution from triage.** Do NOT use it based on:

- The reporter saying "it doesn't reproduce anymore" — intermittent issues come and go; the problem still exists
- Another engineer or user being unable to reproduce — different hardware, bandwidth, or timing can hide the issue
- A profile captured during the issue showing an idle state — the capture window may have missed the active period

**WORKSFORME is only valid when:**
- A specific commit or bug is identified that deliberately fixed it → use FIXED or DUPLICATE instead
- The behavior is confirmed to match design intent → use INVALID instead

**When the reporter provides a profile captured during the issue AND says it no longer reproduces:**
- Analyze the profile for root cause (Step 2c) — the issue was real when the profile was captured
- If the profile reveals a root cause → §1b, pursue investigation
- If the profile is inconclusive → leave the bug open, add a comment acknowledging the profile and noting the intermittent nature; set P3/S3 and add to the relevant meta bug blocker

Show draft in same format as above. Apply dedup check — skip any action whose value is already set. Post only on `apply {id}`.

### Watch list cleanup on handoff

Whenever a bug is handed off outside the A/V triage scope — whether by reassigning
to a different component, by pinging a developer from another team (e.g. Graphics,
Networking) to take over, or by closing — always include `bugzilla-cli watch-remove {id}`
in the ACTIONS block. There is no value in monitoring replies on bugs that are no
longer ours to act on.

This applies even when the bug stays in an A/V component but ownership has clearly
passed to another team (e.g. a Graphics developer is now driving it via NI).

---

## Apply / Skip commands

> **Reply mode only.** `apply` performs Bugzilla writes, so it requires reply
> mode (a configured API key — see Setup check). In **read-only mode** there is no
> apply/skip step: the drafts stand as a reviewable record and nothing is written
> back. Skip this whole section when running read-only.

> **Setting `See Also` (relating bugs).** When a refine asks to "set see also",
> add the related bug IDs to the draft's **`see_also_add`** array. Apply writes
> them via `set-fields --see-also-add` (mapping each ID to its canonical BMO URL).
> This requires `bugzilla-cli` ≥ the build that added `--see-also-add`; if the
> installed CLI predates it, the field is silently skipped — so also mention the
> related bug in the **comment** (BMO auto-links the number) as a durable fallback.
> Use `blocks_add` only for a real blocks/meta relationship, never as a stand-in
> for "see also". (Surfaced by bug 2044925.)

- **`apply {id}`** — write the pending JSON first, then run `bugzilla-cli apply {id}`, which posts comment, sets needinfo flags, sets priority/severity, reassigns product/component, adds CC via `set-fields --cc-add` (`cc_add`), adds blockers (`blocks_add`), sets the `regressed_by` relation via `set-fields --regressed-by-add` (`regressed_by_add`), adds See Also relations via `set-fields --see-also-add` (`see_also_add`), assigns the bug via `set-fields --assigned-to`/`--status` (`assigned_to`/`status`), sets resolution/keywords, removes pending file. If any step was already done manually (e.g. comment already posted), skip that step and run the remaining ones individually. If `ni_targets` is non-empty, also runs:
  ```bash
  bugzilla-cli watch-add {id} --title "{title}" --ni {email1} [--ni {email2}]
  ```
  Then append to `triage-log.json`. If this bug revealed a non-obvious triage pattern, use `/firefox-wiki:add` to record it as a `triage/` page. Only record things that would change how you'd triage a similar bug next time:
  - Site-specific failure patterns (symptom + site + what's actually needed to diagnose)
  - Common reporter mistakes that look like real bugs (e.g. self-inflicted pref changes)
  - Component routing hints (which component a symptom really belongs to)
  - Meta bug association patterns (symptom → which meta bug to check first)

  Do not record routine observations or things already obvious from the bug description.
- **`skip {id}`** — delete `~/firefox-triage/pending/bug-{id}.json`, move to next bug. Log decision as `skipped` in `triage-log.json`.

---

## Pending JSON format

`~/firefox-triage/pending/bug-{id}.json`:
```json
{
  "bug_id": 2027000,
  "title": "...",
  "comment": "...",
  "ni_targets": ["user@example.com"],
  "priority": null,
  "severity": null,
  "blocks_add": [],
  "regressed_by_add": [],
  "see_also_add": [],
  "cc_add": [],
  "resolution": null,
  "keywords_add": [],
  "product": null,
  "component": null,
  "status": null,
  "assigned_to": null,
  "created_at": "2026-04-02T10:00:00Z",
  "bug_context": {
    "description_excerpt": "First ~500 chars of description, plain text",
    "platform": "Windows 10 x64",
    "firefox_version": "150.0",
    "reporter_email": "user@example.com",
    "reporter_name": "Real Name (or empty if absent)",
    "assigned_to": "",
    "assigned_to_name": "",
    "filed": "2026-05-20T16:55:09Z",
    "last_activity": "2026-05-22T14:08:00Z",
    "affected_versions": "all",
    "current_severity": "S3",
    "current_priority": "P3",
    "keywords": ["crash", "regression"],
    "inventory_present": ["platform / version", "STR", "profiler link"],
    "inventory_missing": ["about:support", "media log"],
    "see_also": [
      {"bug_id": 1981503, "label": "regressor"},
      {"bug_id": 2012108, "label": "follow-up fix"}
    ],
    "recent_comments": [
      {"author": "user@example.com",
       "ts": "2026-05-22T09:30:00Z",
       "text": "First ~200 chars of comment..."}
    ],
    "attachments": [
      {"name": "profile.json", "url": "https://...", "size": 412000,
       "content_type": "application/json"}
    ],
    "ai_reasoning": "§1b only: 1–3 sentences on root cause, source files cited, decision logic",
    "change_note": ""
  }
}
```

Set `priority`/`severity` to `null` for §1a (P/S unchanged). Set `keywords_add: ["stalled"]` for stalled bugs. **`cc_add` defaults to empty — do NOT pre-add `$TRIAGE_OWNER`.** Whether the triage owner is CC'd (or needinfo'd) is the owner's per-draft choice via the dashboard's **"CC me" / "NI me"** checkboxes (default **off**); the dashboard adds/removes `$TRIAGE_OWNER` from `cc_add`/`ni_targets` when toggled. Add other CCs to `cc_add` only when genuinely needed. Set `product` and `component` for §1c reassignments (both must be set together); leave `null` otherwise. Set `regressed_by_add: [<bug>]` only when the regressor is actually known (see the Regression note in Step 3); leave `[]` otherwise.

**Assigning a bug for implementation.** When a bug is being taken by a known owner — a §1b you (or a named engineer) will fix, or an explicit "assign to X" refine — set `assigned_to: "<email>"` and `status: "ASSIGNED"`. Apply writes these via `set-fields --assigned-to`/`--status`, which formally assigns the bug, not just a self-NI. Keep the implementer's NI if you're still using it for tracking. Leave both `null` for bugs that stay with the reporter (the §1a/§1c common case). Do not set `assigned_to` to a name — it must be the Bugzilla account email.

The **`bug_context`** object captures the bug's state at draft time so the
triage dashboard can render context-rich cards without re-fetching Bugzilla.
All fields are optional; populate them from the analysis already done in
Steps 2 / 2b / 2c:

- `description_excerpt`: first 400–600 chars of the bug description, plain text (strip Markdown / signatures / inline links).
- `platform` / `firefox_version`: from the bug's environment field, or from about:support if it's attached.
- `reporter_email` / `reporter_name`: bug's `creator` and `creator_detail.real_name`.
- `assigned_to` / `assigned_to_name`: bug's `assigned_to` and `assigned_to_detail.real_name`. Leave both `""` when the bug is unassigned (`assigned_to` is `nobody@mozilla.org`). The dashboard's `taken` rail tag and the card's `Assigned:` chip key off these.
- `filed`: bug's `creation_time` (ISO 8601 UTC) — when the bug was filed. Powers the dashboard's "New" rail tag (shown when filed within the last 7 days) and the "filed" line on the card. **Mandatory on every (re-)draft** — populate it from the bug's `creation_time` and never drop it, including on §1c reassignments and watch-poll re-triages. A missing `filed` silently loses the NEW tag (surfaced by bug 2043943, whose re-triage dropped it).
- `last_activity`: bug's `last_change_time` (ISO 8601 UTC).
- `affected_versions`: which Firefox versions the issue affects — a triage judgment shown on the card's version line (alongside `firefox_version`, the version it was *reported* on). Use `"all"` when the issue isn't version-specific (the common case). When a regression range is identified, give a bounded value like `"151+"`, `"since 150"`, or `"150.0–151"`. Use a single version (e.g. `"Nightly 152"`) only when the issue is confirmed specific to it. Leave `""` if genuinely unknown. Do NOT invent a range — default to `"all"` unless a regressor or version evidence narrows it.
- `current_severity` / `current_priority`: the bug's CURRENT severity/priority *on Bugzilla* at draft time — NOT what this draft is setting. Empty string when unset. These power the dashboard's per-row P/S status tag (`S3·P3` when both set, `no P/S` otherwise).
- `keywords`: the bug's full keywords list from Bugzilla (e.g. `["crash", "regression", "stalled"]`). Powers the dashboard's `crash` rail tag.
- `inventory_present` / `inventory_missing`: the same ✓/✗ items shown in the DRAFT preview block (the inventory from Step 2). Each entry is a short label like `"platform / version"` or `"media log"`.
- `see_also`: list of `{bug_id, label}` for regressors, follow-up fixes, related bugs, duplicates. Pull from the bug's `see_also` field plus your Step 4 findings.
- `recent_comments`: the 2–3 most recent substantive comments, each excerpted to ~200 chars. Skip BugBot / triage-bot / automation comments.
- `attachments`: profiler captures, log files, screenshots, etc. Each: `{name, url, size?, content_type?}`. Populate `content_type` from the attachment's Bugzilla MIME type (e.g. `image/png`, `video/mp4`, `application/json`) — the dashboard uses it to detect images/videos *exactly*, so a screenshot or recording attached with a descriptive, extension-less name still previews in the in-page lightbox. Falls back to the filename extension when `content_type` is absent.
- `ai_reasoning` (§1b only): the source files cited, the S/P justification, the proposed fix area. 1–3 sentences.
- `change_note`: a one-line brief of what changed when the bug **moved out of Awaiting** into this tab on a re-triage (e.g. "Reporter attached a media log → re-triaged §1b"). The dashboard renders it as a "Changed since Awaiting" row. Leave `""` for a bug that was not previously awaiting. Do NOT set it for a non-substantive reply that kept the bug in Awaiting (per the watch-poll handling above, such a bug stays watched and gets no draft).

---

## Known Meta Bugs

The live list is fetched at session start (see Setup check). The table below is a
**fallback** used when the live query fails, and a reference for aliases. Prefer
the live `$META_BUGS` results during Step 4b.

| Alias | Bug | Area |
|---|---|---|
| *(none)* | 1015800 | EME / Encrypted Media Extensions |
| `dropped-frames` | 1416090 | Video frames dropped |
| *(none)* | 1752052 | Media Foundation Playback & CDM Support |
| `video-perf` | 1445470 | Video playback performance (CPU, GPU, power) |
| `webvtt` | 2010319 | WebVTT interop |
| `hw-ffvpx` | 1893427 | HW-accelerated video decoding through ffvpx |
| `wakelock` | 1665980 | Wake lock |
| `media-control` | 1572869 | Media session / OS media controls |
| `mfcdm` | 1806566 | Media Foundation CDM / PlayReady on Windows |
| `autoplay` | 2023365 | Autoplay issues |
| *(none)* | 1790066 | Twitter / X audio/video issues |
| *(none)* | 1904915 | YouTube playback issues |
| *(none)* | 1954546 | Twitch audio/video freezes/stutters |
| *(none)* | 1770250 | Reddit media playback issues |
| *(none)* | 1997593 | Bluesky media issues |
| *(none)* | 1951155 | Audio crackling / chipping |
| *(none)* | 2011679 | Bluetooth device audio/video issues |
| *(none)* | 1676924 | 4K+ video frame drops |
| *(none)* | 1902427 | HDR video playback on Windows |
| *(none)* | 1610199 | Linux VAAPI / ffmpeg video playback |
| *(none)* | 1766429 | Linux playback meta |
| *(none)* | 1648826 | AArch64 macOS media support |
| *(none)* | 1452683 | AV1 playback support |
| *(none)* | 1422891 | MKV / Matroska container support |
| *(none)* | 1884199 | Video startup perf / time to first frame |
| *(none)* | 1746557 | WebCodecs API implementation |
| *(none)* | 2023379 | Media-related sleep/wake issues |
| *(none)* | 2026773 | Remove AudioChannelService / AudioChannelAgent |

Also check the meta bug's open dependency list for existing duplicates of the new bug.

---

## Media Log Instructions

**For audio / video / performance bugs, the media-log capture is the single most useful
diagnostic — make it the FIRST item in "Next Steps"**, with the concrete steps spelled
out (not a vague "use the media preset" line). The only exception: if high-risk `media.*`
prefs were found (see the high-risk-prefs step), lead with the pref reset + restart and
make the capture the **next** item ("if it still persists after the reset, capture…").
Do not bury the capture as the last bullet.

The capture is driven from `about:logging` using the **"Logging to the Firefox Profiler"**
output mode — it produces a **Firefox Profiler profile that the reporter uploads, and they
give us the share URL**. It is **NOT** a `.moz_log` file, and do **not** send the reporter
to profiler.firefox.com directly to start it — it is started from `about:logging` with the
right preset. Always use an inline hyperlink on the words "instruction video" — never
reference-style `[N]` footnotes. Spell out the steps:

> Please capture a profile: open `about:logging`, on the **Logging presets** tab choose the
> **"Media playback"** preset, and under **Logging output** select **"Logging to the Firefox
> Profiler"**. Click **Start Logging**, reproduce the issue from a fresh page load, then
> click **Stop Logging** — the captured profile opens in the Firefox Profiler. Click **Upload
> Local Profile** (the share button) and paste the resulting **share URL** here. The
> [instruction video](https://www.loom.com/share/24ea3a8e3a054c478de94643a0ea8620?sid=87b0ffaa-c4ea-43ce-8107-639f24b747a8)
> walks through it. If you have privacy concerns about the profile or the media content,
> email it to media-alerts@mozilla.com instead.

Use the **Graphics** preset (same flow) instead of / in addition to **Media playback** when
the issue is in the GPU/compositor/overlay path rather than playback. When a pref reset /
workaround precedes the capture (the high-risk-prefs case), prefix it with "If the issue
still persists after the reset, …".

---

## Skill boundaries

| Skill | Responsibility |
|---|---|
| `/triage` | Info completeness, duplicate detection, P/S assessment, NI + meta bug blocking, Bugzilla writes |
| `/bug-start` | Deep code investigation, root cause analysis, implementation planning |
| `/firefox-implementation` | Writing and landing the patch |
