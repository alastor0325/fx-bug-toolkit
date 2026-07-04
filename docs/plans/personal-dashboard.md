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
- **Identity / credentials:** dashboard is **personal** (`alwu@mozilla.com`), not
  the triage bot. New env vars live in `~/.config/secrets/api-keys.env`
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
