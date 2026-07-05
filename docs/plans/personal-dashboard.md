# Plan — Personal Dashboard (`/open-dashboard`)

A personal work dashboard for Firefox contribution flow: collect **needinfos on
me**, **bugs assigned to me**, **Phabricator reviews requested of me**, and **my
own revisions needing my action** into one local page — then, in later stages,
let Claude *act* on selected items (analyze + draft NI replies, run `/review`).

Status legend: 🔴 not started · 🟡 in progress · 🟢 done. Update as checkpoints land.

---

## Decisions locked (from planning Q&A)

- **Buckets (all four):** needinfo-of-me · assigned-to-me · reviews-requested-of-me
  · my-revisions-needing-my-action.
- **Viewer packaging:** standalone dashboard viewer (own dir + `serve.py`-style
  launcher, own port default **9010**, `FX_DASHBOARD_PORT` override). *Not*
  bolted onto `viewer/`.
- **Freshness:** always re-collect on each `/open-dashboard` (no TTL cache).
- **Style:** shared CSS asset (`assets/theme.css`) extracted from the current
  viewer, imported by **both** the investigation viewer and the dashboard →
  single source of truth. A reference skill documents the system.
- **Identity / credentials:** dashboard is **personal** (your own Bugzilla
  account, *not* the shared triage bot). Never hardcode a real email in code,
  tests, or fixtures — use a placeholder like `you@example.com`; the real
  identity comes only from env at runtime (`FX_DASHBOARD_USER`, or the key owner
  via `whoami`). New env vars live in `~/.config/secrets/api-keys.env`
  (same file as `$BMO_API_KEY`):
  - **`BUGZILLA_API_KEY`** = personal BMO key (value copied from `$BMO_API_KEY`);
    this is exactly the var `bugzilla-cli` now reads for personal auth.
  - a Phabricator Conduit token var (pasted from
    `phabricator.services.mozilla.com`).
  Key is passed to `bugzilla-cli` via **env var, never on argv**.
- **Bugzilla queries:** via `bugzilla-cli` (being extended — see Dependencies).
  `bugzilla-cli` alone previously couldn't do these and was wired to the *bot*
  identity; the extension adds personal-list queries + personal auth.
- **Phabricator queries:** Conduit `differential.revision.search` directly (no
  `~/.arcrc` / `moz-phab` present).

### Provisional names (change freely)
- Data-collection + view skill: `/open-dashboard`.
- Style reference skill: `/fx-style`.
- Stage-2 feedback-processing internal skill: TBD (see Stage 2).

---

## Dependencies

- **`bugzilla-cli` extension** (`~/projects/bugzilla-cli`) — 🟢 **done**
  (commit `81ec709`, pushed to `main`; dev-loop verified, 69 tests green;
  `make install` relinked the PATH binary to the dev build). Adds:
  - `bugzilla-cli assigned  --user <email> [--json]` — open bugs assigned to user
    (`assigned_to=<email>` + `resolution=---`).
  - `bugzilla-cli needinfos --user <email> [--json]` — bugs where user is an
    active `needinfo?` requestee (`quicksearch=flag:needinfo?<email>`).
  - personal-identity auth via env var **`BUGZILLA_API_KEY`** (precedence:
    `BUGZILLA_API_KEY` → `BUGZILLA_BOT_API_KEY`/secrets → anonymous; never on
    argv). Existing commands unchanged when it's unset.
  - `--json` → pretty JSON array to **stdout only** (count to stderr); each obj
    includes `{id, summary, status, last_change_time, assigned_to, flags}`.
  Stage 1's Bugzilla path is now unblocked. (Phabricator path is independent.)

---

## Stage 1 — Collect + render (the dashboard itself)  🔴

Skill does the operations and emits data; the page just renders it.

**Checkpoints**
- [ ] **1a. Shared theme.** Extract viewer tokens/base components into
      `assets/theme.css` (palette, IBM Plex Mono/Sans, backdrop, chips, focus
      ring, scrollbars, radii/borders). Refactor `viewer/viewer.html` to consume
      it; each `serve.py` maps the URL `/theme.css` → repo-root
      `assets/theme.css` via a testable path-resolution helper
      (`DIR.parent/"assets"/"theme.css"`; works in-repo and in the installed
      plugin cache). No visual regression in the investigation viewer (e2e check).

**Secrets rule (applies to all collector code + tests):** API keys/tokens are
read from env (`BUGZILLA_API_KEY`, `FX_PHABRICATOR_TOKEN`) at runtime only —
**never hardcoded, never committed, never written into `data.json`**. Tests use
dummy/fake env values + mocked network; no real secret ever appears in a test or
fixture.
- [ ] **1b. `/fx-style` reference skill.** Document the token vocabulary +
      component patterns + do/don'ts + the rule "any new UI imports
      `assets/theme.css` and follows this system." Invoked when building/reviewing
      UI in this project.
- [ ] **1c. Credentials wiring.** Add the personal BMO key var + Phab Conduit
      token var to `~/.config/secrets/api-keys.env`; document + check in `/init`.
- [ ] **1d. Collector** `dashboard/collect.py` (pure logic extracted &
      unit-tested) → writes git-ignored `dashboard/data.json`. Four buckets,
      normalized to `{id, title, url, updated, age_days, status}`.
      - needinfo-of-me, assigned-to-me → `bugzilla-cli` (dep above)
      - reviews-of-me → Conduit `differential.revision.search` (reviewer=me,
        needs-review / blocking)
      - my-revisions-needing-action → Conduit (author=me, status
        `needs-revision` or `accepted`)
- [ ] **1e. Dashboard viewer** `dashboard/dashboard.html` imports
      `/theme.css`; **each bucket is its own clearly-delineated section** (labeled
      header + count + its items), not a merged list. Sortable by staleness, items
      link out to BMO / Phabricator. **This layout needs a UX review pass**
      (`frontend-design`) before it's considered done — clear visual separation
      per part is a hard requirement.
- [ ] **1f. Launcher** `dashboard/serve.py` (127.0.0.1, `.run/` pidfile, port
      fallback, default 9010). Always re-collects on open.
- [ ] **1g. Dev-loop close-out.** Python unit tests (collector) + viewer
      logic/e2e; README; `/sync-tutorial`; version bump + `claude plugin
      tag --push`; CI green.

---

## Stage 2 — Act on selected items (analyze + draft)  🔴

Dashboard becomes actionable: Claude analyzes selected items and drafts a
response, in a back-and-forth loop. **Selection is explicit — never "do all."**

Two action tracks:

### 2a. Needinfo handling
- Exclude **NIs from myself** (only NIs *requested of* me).
- For a selected NI: read what the NI is asking, analyze the problem, produce a
  **suggestion + draft reply**.
- **Selection model (OPEN — decide in Stage 2 kickoff):**
  - Option A: user hand-picks which NIs to handle (from the page).
  - Option B: auto-process NIs within a recent window (e.g. "within a week" —
    range is *provisional / uncertain*).
  - Likely: A as default, B as an optional batch mode.

### 2b. Review-request handling
- For selected review requests, auto-triage / run `/review` on them.
- Again **not all** — user chooses which; Claude processes the chosen set later.

### 2c. Feedback-processing internal skill (the back-and-forth)
- A dedicated **internal skill** (not user-triggered directly — invoked by the
  dashboard drain, à la `triage-apply-feedback`) that takes the user's
  selections + feedback and (re)drafts NI replies / review outputs.
- Persists pending drafts the dashboard reads back (mirror the `/triage` →
  pending drafts → dashboard → refine-feedback pattern already in the toolkit).

**Open questions to resolve at Stage 2 kickoff**
- [ ] Exact NI-selection condition (hand-pick vs time-window vs both; window length).
- [ ] Where selection lives (interactive on the page? a written selection file?).
- [ ] Draft storage location + schema; how drafts surface back on the page.
- [ ] How the internal feedback skill is triggered (queue drain prompt vs manual).
- [ ] Whether NI drafts are ever auto-posted or always human-gated (default: gated).

### 2d. Interactive triage cards — user vision (captured 2026-07-04)
Refines the whole dashboard from a link list into an **interactive triage
surface**. Supersedes the v2 "unified urgency queue"; back to **distinct
sections**, each item an **expandable card** with a brief + triage-style tags +
action buttons that hook into existing skills.

- **Sections (3):** Needinfos · Review requests · Bugs I'm working on. (The
  earlier "my revisions land/fix" folds into "Bugs I'm working on" as patch
  status.)
- **NI card:** title does NOT link straight to the bug. Shows a **brief** ("what
  the bug is about" + "what the NI is asking") + **tags** (category/characteristics
  — reuse `/triage`'s vocabulary). **Click → expand** → buttons: *Draft reply* /
  *Bug investigate*, following the `/triage` draft flow. If the bug already has
  everything needed to solve it → **auto-run `/bug-start`** and show a brief
  proposed solution.
- **Review card:** brief of what the review is for; **expand** → more info + a
  *Run `/review`* button.
- **Bugs I'm working on:** list my active bugs with **my patch status** (WIP / in
  review / needs-revision / accepted / landed) + triage-style tags.

**Decisions (2026-07-04) — the model is "triage for your inbox":**

*Two explicit Claude passes; the HTML only ever displays generated JSON.*

- **① Generation pass (like `/triage`).** Running the skill does a full pass over
  your NIs / review-requests / my-bugs and **generates everything up front** into
  the data file: field-derived **tags**, a **deep brief** per item ("what the bug
  is about" + "what the NI/review is for"), and the **solvability gate** result
  (whether to offer a "run /bug-start?" suggestion). LLM cost lives here, once per
  run — exactly like `/triage`. The page does **not** compute briefs lazily; it
  shows what generation produced. (Supersedes the earlier "hybrid/on-expand"
  idea — expanding a card just reveals the already-generated brief.)
- **② Drain pass (explicit command).** Card buttons (Draft reply · Run /review ·
  Run /bug-start) write requests to a **queue file**; you run an explicit drain
  command in the terminal (e.g. `/open-dashboard drain` or a "Process queue"
  prompt) and Claude processes them all at once, writing results back for the
  page to show. The page never calls Claude directly. (A separate project that
  talks to Claude live is out of scope here.)
- **Draft-only by default, opt-in posting** — mirrors `/triage`: default produces
  drafts/analyses locally and makes **no** external writes; an opt-in mode can
  post NI replies / review comments per item (needs write-scoped creds).
- **Card tags = Core set** (field-derived, no LLM): component · severity (S) ·
  security · regression. Deeper labels (completeness, duplicate-suspect,
  solvable) come from the generation pass.
- **"Bugs I'm working on" scope = union**: assigned-to-me OR has an open
  Phabricator revision; patch status (WIP / in-review / needs-revision /
  accepted / landed) shown where a revision exists.
- **Auto-`/bug-start` = suggest-only.** The generation pass's solvability gate
  decides whether a card shows a "looks ready → run /bug-start?" button; nothing
  runs until you click it (→ queued → drained).

**Decisions (round 3, 2026-07-04):**
- **Separate generate + open** (like `/triage` + `/open-triage`). A heavy
  *generate* command produces the data; **`/open-dashboard` serves the last
  generated result instantly** and never blocks on analysis.
  - **First use (no data yet):** the page shows a **processing animation** while
    the first generation runs.
  - **Subsequent uses:** **quick-load the last result immediately**; show a
    subtle "analyzing…" indicator when a new generation is running in the
    background, then refresh in place when it completes.
  - ⇒ generation writes a **status/progress signal** (e.g. a small status file:
    idle / running / done + timestamp) the page polls to decide what to show.
- **"Bugs I'm working on" = display-only for the MVP** (brief + tags + patch
  status). Action buttons (address-review, nudge, land) are a **post-MVP**
  add-on.

**Still-open (minor / at implementation):**
- [ ] Command names (generate vs `/open-dashboard` vs `drain`).
- [ ] Draft/result + queue + status storage schema; how results surface on cards.
- [ ] Processing-animation + background-refresh mechanics (poll the status file).

---

## Stage 2 — Build order (agreed 2026-07-04)  🔴

Build the producer before the consumer, so each phase is testable against a real
contract. Follow the fx-bug-toolkit Dev Loop for every phase (tests green,
README, `/sync-tutorial` when the viewer changes, release, CI green). Keep
secrets in env only; no real email anywhere ([[no-real-email-in-code]]).

### Phase A — Generate skill (the heavy `/triage`-style pass)  🔴
Produces the v3 data file the HTML displays. LLM cost lives here, once per run.
- [ ] **A1. Define the v3 data schema** (the contract for Phase B): per section
      (`needinfos` / `reviews` / `my_bugs`), each item carries
      `{id, url, title, waiting_days, tags[], brief, ...}` where `brief` =
      generated summary ("what the bug is about" + "what the NI/review is for"),
      `tags` = Core field-derived set (component · severity · security ·
      regression), plus per-type extras: NI → `from`, `solvable` (gate);
      review → `author`; my_bugs → `patch_status`
      (wip/in-review/needs-revision/accepted/landed). Plus top-level
      `generated_at`, `user`, and a **status/progress signal**.
- [ ] **A2. Fast gather** — reuse/extend `collect.py` for the field data
      (bugzilla-cli needinfos/assigned + Phabricator reviews/mine + my-bugs union
      = assigned OR has-open-revision). No LLM here.
- [ ] **A3. LLM enrichment** — per item: deep brief, any deep tags, and the
      solvability gate. This is the skill's own reasoning (like `/triage`), not
      `collect.py`. Write the enriched data file + status file.
- [ ] **A4. Skill** `skills/<generate-name>/SKILL.md` (heavy pass, explicit run).
- [ ] **A5. Tests** — pure enrichment/merge/schema-shaping logic unit-tested
      against **mock backend** payloads (no live BMO/Phab, no real email); status
      file written correctly.

### Phase B — Update the HTML to the v3 card design  🔴
Pure display of Phase A's data; no Claude calls from the page.
- [ ] **B1. Three sections** (Needinfos · Review requests · Bugs I'm working on),
      replacing the v2 unified-queue layout, on `/theme.css` + `/fx-style`.
- [ ] **B2. Expandable cards** — collapsed: tags + one-line brief; expanded: full
      brief + (Phase C) action buttons. NI/review buttons; my_bugs display-only
      (MVP).
- [ ] **B3. Load-last-instantly + processing states** — serve the last result at
      once; **first use (no data) → processing animation**; **"analyzing…"**
      indicator when a generation is running (poll the status file); refresh in
      place on completion.
- [ ] **B4. Tests** — `dashboard.logic.js` units for section grouping, tag/brief
      rendering, status-driven processing/loaded/empty states; e2e for expand +
      the processing/loaded transition.
- [ ] **B5. `/open-dashboard` skill** — serve-only launcher (Task 5); wire creds
      into `/init`, README, `/sync-tutorial`.

### Phase C — Drain skill (execute queued card actions)  🔴
- [ ] **C1. Queue + results + status schema** — buttons (Draft reply · Run
      /review · Run /bug-start) append to a queue file the page writes; drain
      writes results the page reads back onto the card.
- [ ] **C2. Drain skill** — explicit command; processes the whole queue at once
      via the existing flows (`/triage` draft flow, `/review`, `/bug-start`).
      **Draft-only by default**, opt-in posting like `/triage`.
- [ ] **C3. Tests** — queue parse/dedup, per-action dispatch, result write-back,
      draft-only guard (no external writes unless posting mode) — mock backends.

---

## Stage 3+ — (reserved)  🔴
Placeholder for further checkpoints (e.g. assigned-bug triage assist, batching,
notifications). Add as they surface.

---

## Notes
- Follow the fx-bug-toolkit Dev Loop for every implementation checkpoint (tests
  pass, README, `/sync-tutorial`, release, CI green).
- No personal data / machine paths in shipped files; `dashboard/data.json` is
  git-ignored like `viewer/index.json`.
