# Changelog

All notable changes to **fx-bug-toolkit** are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/). Each released version has a matching
`fx-bug-toolkit--vX.Y.Z` git tag.

## [Unreleased]

_Nothing user-facing yet._

## [0.6.3] — 2026-06-30

### Fixed
- **Investigation viewer no longer jumps to the top.** Returning to the tab,
  switching back from another app/terminal, or coming back from a link opened in
  a new tab no longer snaps the detail pane to the top. The background refresh
  (visibilitychange/focus) now **leaves the open doc untouched** when its content
  is unchanged — it no longer re-renders `#detail` and tries to restore scroll
  (which lost the position under real-browser scroll-anchoring); a genuinely
  changed doc still re-renders and preserves scroll, and switching to a different
  doc still starts at the top.
- **Viewer assets are served `Cache-Control: no-store`.** `serve.py` previously
  no-stored only `index.json`, so browsers heuristically cached `viewer.html` /
  `viewer.logic.js` and an open tab could keep running stale code after an update.
  Every response is now `no-store`, so a reload always loads current code.

### Added
- **`/bug-start` deep-mode write-up gains a "Hypotheses Ruled Out" section** —
  records the dead ends an investigation eliminated, not just the final root cause.

## [0.6.2] — 2026-06-24

### Changed
- **`/review` security dimension catches lifetime-contract UAFs.** The `security`
  reviewer now has explicit checks for a class of use-after-free its generic
  "lifetime & ownership" bullet didn't reliably prompt for: (1) **self-registration
  / observer-listener lifetime** — when an object registers itself into a
  longer-lived manager that holds it by strong `RefPtr` while keeping a raw
  back-reference to a shorter-lived owner, prove it is unregistered on **every**
  teardown path (destructor, error/cancel/shutdown, **and** cycle-collection
  `Unlink`), not just on a happy-path event a peer may never deliver; (2)
  **cycle-collection completeness** — every member that joins a ref cycle or holds
  an external registration must appear in both Traverse and Unlink (a member omitted
  from `Unlink`, or a subclass member while the CC macro is on the base class, is a
  classic UAF/leak); (3) **unproven lifetime contracts** — a "Shutdown runs before
  release" / "A outlives B" comment is a claim to verify on all paths, not to trust.
- **`/open-review` requires Revue ≥ 0.2.1** (was ≥ 0.2.0). 0.2.1 resolves HEAD by
  reading git's on-disk ref files instead of spawning `git rev-parse` via blocking
  `execSync`, so the dashboard stays responsive when concurrent git/jj activity
  repacks objects / rewrites `packed-refs` in the same checkout. Still carries the
  0.2.0 esr/non-main-worktree ENOBUFS fix (without which those worktrees won't open).

## [0.6.1] — 2026-06-18

### Added
- **`spec-check` prefers [`webspec-index`](https://github.com/jnjaeschke/webspec-index)
  for web specs.** When the `webspec-index` CLI is on `PATH`, `spec-check` now
  reads WHATWG/W3C/TC39 sections through it instead of `WebFetch` — it returns
  the **exact section** (no truncation of the multi-MB single-page HTML),
  validates anchors (`exists`), and can surface cross-references and unlanded
  WHATWG-PR previews (`--pr N`). It **falls back to `WebFetch`** when not
  installed, and **codec / container / protocol** specs (H.26x, ITU-T, ISO/IEC,
  RFCs) stay on `WebFetch`. Listed as an optional dependency (`cargo install
  webspec-index`); wiring it into `/init` is a tracked follow-up.

### Changed
- **`/open-review` now requires Revue ≥ 0.2.0.** Below 0.2.0, opening an
  esr/non-main worktree failed with `spawnSync /bin/sh ENOBUFS` because Revue
  diffed against `origin/main` (mozilla-central), spanning tens of thousands of
  commits. 0.2.0 resolves the diff base from the branch's upstream, so
  esr/beta-uplift worktrees show only their own patches. (Fixes #47.)
- **`/update` and `/init` report CLI installs as version deltas.** A `cargo
  install` can compile for minutes with no hint why, so a routine refresh looked
  broken. `/update` now prints a per-CLI delta (`already current (X)`,
  `<old> → <new> (updated)`, or `installed (X)`) and `/init` echoes the installed
  version. Pure visibility — no change to what compiles or to the pinned
  versions.

## [0.6.0] — 2026-06-12

### Changed
- **`/review` is now a multi-aspect reviewer.** Instead of one pass over the
  whole patch, `/review` understands the series, **routes** it to the review
  dimensions that apply, fans each out to a `firefox-review-aspect` worker in its
  own context, **adversarially verifies** every BLOCKER/IMPORTANT finding (a
  skeptic re-checks it against the real code; refuted findings are dropped before
  they reach you), then writes one structured document. The doc now records which
  dimensions ran vs. were skipped and the verification counts, and `/review`
  prints the document's absolute path as its final line so callers locate it
  directly. The orchestration runs in the `/review` skill (the main session), so
  it can fan the work out to subagents.
- **`security` and `threading` always run, at the highest standard, on every code
  change.** `security` is a dedicated memory-corruption pass — use-after-free,
  use-after-move, double-free, dangling pointers, out-of-bounds, integer overflow
  feeding an allocation or index, uninitialized memory, type confusion, ownership
  / refcount, and untrusted-input validation — with an adversarial, default-to-flag
  posture (UAF/OOB/corruption is always a BLOCKER). `threading` covers data races,
  lock ordering / deadlock, re-entrancy, and TOCTOU. `spec`, `code-quality`, and
  `tests` also always run; `ipc`, `error-handling`, and `api-usage` are added when
  the diff touches them.

### Added
- **`firefox-review-aspect` agent** — the single-dimension reviewer/verifier
  `/review` fans out to.

### Removed
- The single-pass `firefox-review` orchestrator agent (its role moved into the
  `/review` skill).

## [0.5.1] — 2026-06-11

### Fixed
- **Investigation viewer (`/open-investigation`) no longer shows stale results
  while left open.** It fetched `index.json` once at page load and never again,
  so an open tab kept showing the page-load snapshot — search and the list (and
  the collapsed-sidebar search dropdown) didn't reflect investigations added or
  edited afterward by `/triage`, `/bug-start`, etc. The viewer now re-fetches
  when you return to it — on `visibilitychange` (tab switch / un-minimize) **and**
  `window` focus (switching back from a terminal beside a still-visible tab) —
  preserving the open document across the refresh. (The server already rebuilt
  `index.json` on every request; only the client re-fetch was missing.)

## [0.5.0] — 2026-06-09

### Added
- **`/triage` surfaces already-pending needinfos.** Each draft now captures the
  bug's *outstanding* needinfo flags (set by anyone — the reporter, another dev,
  an earlier triage) into `bug_context.pending_needinfos` `{requestee, setter,
  since}`, read from the same `bugzilla-cli get` flags the dedup check already
  uses. The triage dashboard renders these as a **Pending NI** row and turns a
  chip red when a draft's `ni_targets` re-request an already-pending requestee —
  a no-op on BMO (it collapses a duplicate needinfo into the existing flag) — so
  a redundant NI is visible before apply. Motivated by a queue drain where
  applies re-set needinfos the reporter had already filed.

### Changed
- **Triage dashboard pinned to v0.5.0** (`/open-triage`, `/update`), which adds
  the Pending NI row.

## [0.4.10] — 2026-06-09

### Fixed
- **`/bug-start` no longer emits broken searchfox links.** It was building
  revision-pinned URLs with a **fabricated** commit hash, so every source link
  404'd (e.g. bug 2045281). It now **resolves the revision searchfox has actually
  indexed** (from `firefox-main`'s `/source/` page) and pins every link to that —
  stable *and* valid — with an explicit rule to **never guess a hash** and a
  fallback to the non-pinned `/source/` form when resolution fails. The
  `source-links` Golden Rule was tightened to match.

### Added
- **`/bug-start` verifies its own links before finishing** — it `curl`s every URL
  in the written investigation and flags any that don't return `200`, so a stale
  path, wrong line, or bad pin is caught and fixed before the file is done.

## [0.4.9] — 2026-06-09

### Fixed
- **Stale triage-dashboard port in docs.** `/triage` Step 7 and the tutorial said
  the board serves at `127.0.0.1:8765`; `/open-triage`'s default has been **9001**
  since v0.4.7. Both now say `9001` and note the free-port fallback.

## [0.4.8] — 2026-06-09

### Fixed
- **`bmo-to-md` API-key env var corrected to `BMO_API_KEY`.** `/bug-start`'s
  security-bug fallback documented it as reading `$BUGZILLA_API_KEY`, which is
  wrong — `bmo-to-md` reads **`BMO_API_KEY`**. (Distinct from `bugzilla-cli`'s
  reply-mode `BUGZILLA_BOT_API_KEY`, which is unchanged.) The tutorial now notes
  the same var for reading private/security bugs.

## [0.4.7] — 2026-06-08

### Changed
- **`/open-triage` now serves on a stable default port, 9001**, instead of an
  auto-picked free port — so you can bookmark `http://127.0.0.1:9001/` and return
  to the board. A re-run reuses a dashboard already answering on 9001 (or the
  last-used port); if 9001 is taken by another app it falls back to a free port
  and prints the one it used. `PORT` still forces a specific port (honored as-is —
  no fallback, no reuse-shadowing), matching the viewer's `serve.py` rule. 6000 is
  deliberately avoided — browsers block it as an unsafe port
  ([WHATWG Fetch §port-blocking](https://fetch.spec.whatwg.org/#port-blocking)).

## [0.4.6] — 2026-06-08

### Fixed
- **`/triage` no longer breaks on Windows git-bash.** Its "Merge results" step
  called bare `python3` (×4) — but Windows git-bash typically only has `python`
  on PATH, so the triage-log merge and the deferred `watch-add` drain failed
  there. It now resolves `PY="$(command -v python3 || command -v python)"` first
  and calls `"$PY"`, matching the other skills. Also hardened the same pattern in
  `download-guard` for consistency. (macOS/Linux unaffected.)

## [0.4.5] — 2026-06-08

### Changed
- **`/update` now also refreshes the firefox-wiki plugin when it's installed.**
  If the optional Accumulated Knowledge Database plugin
  (`firefox-wiki@firefox-wiki-plugin`) is present, `/update` runs
  `claude plugin marketplace update` + `claude plugin update` on it too; if it's
  not installed, it's skipped silently (never auto-installed). The wiki *content*
  (`$WIKI_PATH`) is separate and untouched.
- **Tutorial: the wiki plugin now installs directly** — `claude plugin
  marketplace add alastor0325/firefox-wiki-plugin` (no `git clone` of the plugin
  repo first), matching how fx-bug-toolkit itself installs.

## [0.4.4] — 2026-06-08

### Changed
- **The investigations viewer (`/open-investigation`) now defaults to port 9000**
  instead of auto-picking a free port. `FX_VIEWER_PORT` still overrides, a running
  instance is still reused, and if 9000 is already taken by another app the
  launcher falls back to a free port (and prints it) so it never hard-fails. Gives
  the viewer a stable, bookmarkable URL (`http://127.0.0.1:9000/viewer.html`),
  matching `/open-review`'s fixed-port behavior.

## [0.4.3] — 2026-06-08

### Changed
- **`/open-review` defaults to a stable port and stops prompting for a worktree**
  ([#22](https://github.com/alastor0325/fx-bug-toolkit/issues/22)). It now serves
  on **7779** (bookmarkable), falling back to a free port only if 7779 is taken,
  and reuses an already-running board. It no longer pre-flights the series or asks
  which worktree to open — it just launches on the resolved repo and lets you
  switch worktrees in Revue's own UI.

### Fixed
- **`/open-review` requires Revue ≥ 0.1.1**
  ([#24](https://github.com/alastor0325/fx-bug-toolkit/issues/24)). Older Revue
  mislabelled sibling-worktree URL hashes (e.g. `#firefox-2045395` instead of
  `#2045395`); the skill now checks `revue --version` and offers to upgrade a
  stale install from GitHub.

## [0.4.2] — 2026-06-08

### Changed
- **Dropped the lock emoji from the `SECURITY` chip** — the red chip already
  stands out; it now reads plain `SECURITY`.

## [0.4.1] — 2026-06-08

### Fixed
- **The investigation viewer now reflects edited/added files on a plain reload.**
  `serve.py` previously built `index.json` only at launch, so editing a file and
  refreshing the browser showed stale data. The server now **rebuilds the index
  on every `index.json` request**, so a reload reflects the current files without
  re-running `/open-investigation`.
- **The sidebar's open/closed state survives a browser reload.** It's persisted
  per-browser (`localStorage`) and restored on load instead of always reopening.

### Added
- **Search results dropdown when the sidebar is collapsed.** Typing in the search
  box used to filter only the (hidden) sidebar list, so a collapsed sidebar made
  search appear to do nothing. With the sidebar folded, matches now appear in a
  dropdown under the search box; click one to open it.
- **`SECURITY` chip on security-bug rows.** Investigations flagged as security
  bugs (a `## Security Rating` section — what `bug-start` writes for any sec-* /
  security-group bug — or an explicit `security: true`) now show a red `SECURITY`
  chip in the list and detail, so they stand out at a glance.

### Changed
- **Complexity moved off the list rows** into the detail pane only, keeping rows
  focused on the high-signal tags (security, folder, depth).

## [0.4.0] — 2026-06-08

### Added
- **`/open-team` — open the Firefox review-team dashboards.** A new command in the
  `/open-*` family that opens [firefox-review-stats](https://alastor0325.github.io/firefox-review-stats/),
  the live, weekly-refreshed per-team dashboards for Firefox review groups
  (within-group review-load distribution, concentration metrics — Top-N share,
  Gini, bus factor — sole-reviewer risk, a per-revision wait queue, and an
  LLM-summarized digest of what each component shipped). It opens the hosted
  GitHub Pages site — the landing picker by default, or a named team
  (`playback`/`webrtc`/`gfx`) straight away. Nothing to install, no local server.
  Added a tutorial chapter (with a screenshot) explaining the views and metrics.

## [0.3.19] — 2026-06-08

### Fixed
- **The viewer now reflects updated investigations.** `viewer.html` fetched
  `index.json` with no cache-busting, so the browser served a stale cached copy
  even though `serve.py` rebuilds the index on every start — the viewer "wouldn't
  catch up" after the investigation dir changed. It now fetches with a per-load
  nonce + `{cache:'no-store'}`, so a reload always shows current data.
- **`bug-start` no longer emits invalid-YAML frontmatter** ([#15](https://github.com/alastor0325/fx-bug-toolkit/issues/15)).
  The agent sometimes improvised Bugzilla-style keys and wrote an unquoted
  `component: Core :: Audio/Video`, whose ` :: ` is invalid YAML (*"mapping
  values are not allowed in this context"*), breaking frontmatter parsers. The
  frontmatter contract is now explicit: use **only** the documented schema fields
  (no ad-hoc `component`/`title`/`assignee`/… keys — those live in the body), and
  **double-quote any value containing a colon**; both templates quote their
  free-text fields. The viewer indexer also now **warns** on a present-but-
  unparseable block instead of silently dropping its metadata.

## [0.3.18] — 2026-06-06

### Changed
- **Renamed the three web-UI launchers to a consistent `/open-*` family**
  (breaking): `/browse` → **`/open-investigation`**, `/triage-dashboard` →
  **`/open-triage`**, `/review-dashboard` → **`/open-review`**. They now group
  together in the slash menu and read in parallel ("open the investigation /
  triage / review UI"). Update any muscle memory or notes; the old names no
  longer resolve. Arguments, behavior, ports, and lazy-install are unchanged.

## [0.3.17] — 2026-06-06

### Changed
- **`bmo-to-md` now installs from crates.io, not GitHub.** `/init` and `/update`
  now run `cargo install bmo-to-md` instead of
  `cargo install --git https://github.com/padenot/bmo-to-md`. The crate on
  crates.io is owned by its author (padenot) and matches the repo, so this is the
  same registry crate — just installed the agent-friendly way that the auto-mode
  classifier doesn't block. Completes the GitHub→registry move for every install
  except `profiler-cli` (upstream isn't on npm yet).

## [0.3.16] — 2026-06-06

### Changed
- **`bugzilla-cli` now installs from crates.io, not GitHub.** `/triage`'s install
  hint and `/update`'s refresh step now run `cargo install bugzilla-cli --version 0.2.0`
  instead of `cargo install --git https://github.com/…--tag v0.2.0`. Same reason as
  the dashboard's PyPI move (0.3.15): a registry install of a named crate isn't
  "code from an external GitHub repo," so Claude Code's auto-mode classifier no
  longer blocks the agent from installing/updating it. (`bugzilla-cli 0.2.0` was
  published to [crates.io](https://crates.io/crates/bugzilla-cli).) The pin-drift
  test now matches the `--version` form.

## [0.3.15] — 2026-06-06

### Changed
- **The triage dashboard now installs from PyPI, not GitHub.** `/triage-dashboard`,
  `/update`, and the dashboard's lazy install/upgrade now run
  `pip install "triage-dashboard==<pinned>"` instead of
  `pip install "git+https://github.com/…@v<pinned>"`. A registry install of a named
  package isn't "code from an external GitHub repo," so Claude Code's auto-mode
  classifier no longer blocks the agent from installing/upgrading the dashboard —
  the whole class of "cyber block" failures on first use and version bumps is gone.
  (The dashboard was published to PyPI as
  [`triage-dashboard`](https://pypi.org/project/triage-dashboard/).)

### Removed
- **The `/init` "pre-authorize the triage dashboard install" step (added in 0.3.13,
  fixed in 0.3.14) is gone.** It existed only to work around the GitHub-install
  block; the PyPI switch removes the trigger entirely, so the `autoMode.allow`
  carve-out and the manual `~/.claude/settings.json` editing are no longer needed.

## [0.3.14] — 2026-06-06

### Fixed
- **The `/init` pre-authorization step now has the *user* add the rule, not the
  agent.** 0.3.13 tried to have the agent merge the `autoMode.allow` carve-out
  into `~/.claude/settings.json` on consent — but Claude Code's classifier
  **hard-blocks** an agent from editing settings to add an `autoMode` rule
  (*Auto-Mode Bypass*: an agent widening what the classifier permits), and that
  `hard_deny` **cannot be cleared by user authorization**. So the agent-run merge
  always failed. `/init` now only **shows** the scoped rule and the detection
  check, and instructs the user to add it themselves — by pasting the JSON into
  `~/.claude/settings.json` or running a one-liner with the `!` prefix (which
  executes as the user's own command), then restarting Claude Code.

## [0.3.13] — 2026-06-06

### Changed
- **`/init` can pre-authorize the triage dashboard install.** Installing the
  dashboard (`pip install git+https://github.com/alastor0325/firefox-triage-dashboard@…`,
  done lazily by `/triage-dashboard` and by `/update`) is code fetched from an
  external GitHub repo, which Claude Code's auto-mode classifier `soft_deny`s — so
  first-use and every version bump could fail with a denial ("installs and executes
  code from an external GitHub repo not in trusted source control"). `/init` now has
  an **optional, opt-in** step that merges a **narrowly-scoped** `autoMode.allow`
  carve-out — naming **only** the dashboard repo, never a `Bash(*)` wildcard, and
  keeping `"$defaults"` so all built-in safety rules stay in force — into the user's
  `~/.claude/settings.json` (the classifier ignores project/plugin-shipped settings).
  Declining is safe: the dashboard still works and the install can be run by hand
  with the `!` prefix.

## [0.3.12] — 2026-06-05

### Changed
- **Pinned dependency versions now have a single source of truth —
  `.claude-plugin/versions.json`** (currently `bugzilla-cli` and the triage
  dashboard; the HEAD-tracked CLIs aren't pinned). The inline skill pins still
  carry the values (skill Bash can't read the manifest at runtime), but a new
  structure test fails if any of them drifts from the manifest — so a dependency
  bump can no longer ship with a half-updated set of pins. Maintenance only; no
  user-facing behaviour change.

## [0.3.11] — 2026-06-05

### Changed
- **Triage read-only mode is now end-to-end.** Pins the triage dashboard to
  **v0.3.0**, which makes the dashboard read-only aware: with no Bugzilla API key
  it shows a "read-only · drafts only" badge and hides every write affordance —
  Apply, the owner *CC me / NI me / Assign me* toggles, and the editable
  will-apply diff with its cc/ni/assign rows — while the Process-queue drain skips
  the apply step. The AI drafts stay fully reviewable; nothing writes back until
  you configure a key.
- **`/triage` read-only drafts no longer assume a bot account.** In read-only
  mode the draft's `ACTIONS ON APPROVAL` blocks are a proposal only, `$BOT_EMAIL`
  is never resolved/referenced, and bot-account-only steps (the §1b "set NI on
  the bot account" ready-for-investigation signal) are skipped.

### Documentation
- **Tutorial explains the two triage modes** — read-only (default, no key, no
  `$TRIAGE_OWNER`) vs reply mode, and how to enable reply mode via `bugzilla-cli`.
  The `$TRIAGE_OWNER` summary is corrected to reply-mode-only.

## [0.3.10] — 2026-06-05

### Changed
- **`triage-apply-feedback` documents that it makes no Bugzilla writes** and is
  mode-independent (read-only vs reply) — it only edits the local pending draft
  plus the wiki/decisions-log, so it needs no API key. Clarifies that the write
  (`apply`) is the drain prompt's reply-mode-only step. (No behaviour change.)

## [0.3.9] — 2026-06-05

### Changed
- **`/triage` now runs read-only by default; reply mode is opt-in.** Triage no
  longer requires a Bugzilla API key (or `$TRIAGE_OWNER`) to run: with no key it
  fetches and drafts everything but makes **no writes** (reads hit BMO's public
  API, so security-restricted bugs aren't visible). If a key is already configured
  it picks **reply mode** automatically; otherwise it asks, defaulting to
  read-only. `$TRIAGE_OWNER` and the `apply`/write steps are now gated on reply
  mode. Requires [`bugzilla-cli`](https://github.com/alastor0325/bugzilla-cli)
  **≥ v0.2.0** (the release that added anonymous reads + a read-only setup mode);
  the install hint is pinned to `--tag v0.2.0`.
- **`bugzilla-cli` is now listed in the README Dependencies table** (it was only
  mentioned in prose), marked required for `/triage` with reads needing no key.

## [0.3.8] — 2026-06-05

### Changed
- **Bump the pinned triage dashboard to v0.2.2.** The dashboard now renders
  `see_also_add` in the Will-apply diff (and dry-run plan) as linked "+see also
  bug N" refs — so a "set see also" refine is visible before you apply, matching
  the new `bugzilla-cli --see-also-add` write path.

## [0.3.7] — 2026-06-05

### Changed
- **`/triage` can now set `See Also` on apply.** `bugzilla-cli` gained
  `set-fields --see-also-add`, so a "set see also" refine now adds the related
  bug IDs to the draft's new `see_also_add` array and apply writes the formal
  *See Also* field (each ID → canonical BMO URL). Supersedes the 0.3.5 note that
  it couldn't be set; the comment-mention is now a fallback for older
  `bugzilla-cli` builds. Requires `bugzilla-cli` ≥ the build that adds
  `--see-also-add`.

## [0.3.6] — 2026-06-05

### Fixed
- **`/update` used the wrong plugin-update command.** It told Claude to run the
  unqualified `claude plugin update fx-bug-toolkit`, which can fail to resolve;
  it now uses the qualified `fx-bug-toolkit@fx-bug-toolkit` form (matching how the
  toolkit is installed and how `claude plugin list` shows it).

### Changed
- **`/update` installs missing required CLIs instead of skipping them.**
  `bmo-to-md`, `searchfox-cli`, and `profiler-cli` are mandatory, so `/update`
  now installs them when absent (and upgrades when present), rather than telling
  you to go run `/init`. It still defers to `/init` when the underlying toolchain
  (`cargo`, or `git`+`node`/`npm`) is missing. Optional pieces (triage dashboard,
  Revue) stay lazily installed and are only refreshed if already present.
- **`/update` no longer rebuilds tools that are already current.** Dropped
  `cargo install --force` (cargo is a no-op when the version/commit is unchanged)
  and `profiler-cli` now rebuilds only when its `git pull` brought new commits —
  so a same-day re-run doesn't trigger pointless recompiles.
- **`/update` ends with a version + changes summary** — the plugin's `vOLD → vNEW`
  with a one-line-per-version changelog highlight, each CLI's outcome, and the
  restart reminder.

## [0.3.5] — 2026-06-05

### Changed
- **`/triage` Apply docs: `See Also` can't be written by apply.** `bugzilla-cli
  set-fields`/`apply` has no see-also field, so a "set see also" refine now
  surfaces the related bug in the **comment** (BMO auto-links) and flags that the
  formal *See Also* entry can be added manually — rather than silently dropping
  it or misusing `blocks_add`. (Surfaced by bug 2044925.)

## [0.3.4] — 2026-06-04

### Changed
- **`/review-dashboard` remembers your repo instead of guessing from the working
  directory.** When run with no path it now reuses Revue's stored default repo
  (`~/.revue/config.json`, set via `revue init`): the first no-argument run asks
  which folder to open and remembers it, then later runs offer that default or a
  different folder. It no longer auto-picks the current directory — under a skill
  the cwd is the Claude session's directory, not necessarily the repo you want to
  review — and it never silently overwrites an existing default. README and the
  tutorial document the remembered-default behaviour.

## [0.3.3] — 2026-06-04

### Changed
- **`/review-dashboard` now explains which folder to open and pre-flights it.**
  Revue shows a worktree's patch series (commits on top of `origin/main`), so the
  skill now teaches you to point it at the folder holding the work — a feature
  branch or a dedicated worktree with unlanded commits, not a clean `main`
  checkout — and checks the series before launching, asking which repo/worktree
  you meant instead of silently opening an empty board. The tutorial's Review
  chapter gained the same guidance.

## [0.3.2] — 2026-06-04

### Fixed
- **`/triage` §1b drafts now needinfo the reporter when they ask for data.** A
  §1b draft (P/S set, root cause investigatable) that requested a media-preset
  profile from the reporter was phrased "No action needed from you" with no NI,
  so the bug never entered Awaiting (bug 2044925). The §1b path now states that
  requesting *any* artifact from the reporter (profile, media log, about:support,
  sample, STR, workaround result) is a reporter needinfo — set `ni_targets` on
  the reporter, never write "no action needed" while asking for data.

## [0.3.1] — 2026-06-04

### Changed
- **`/review`'s output directory is now configurable and lives in a dot folder.**
  Reviews are written to `$FX_REVIEW_DIR` if set, otherwise
  `~/.fx-bug-toolkit/patches-review` (was a hardcoded `~/firefox-patches-review/`),
  matching how `FX_BUG_INVESTIGATION_DIR` works. Added to the README
  Configuration table.

## [0.3.0] — 2026-06-04

### Added
- **`/review` — AI patch review.** Reviews a Firefox patch (`D<rev>`, `local`
  committed branch patches, or uncommitted `diff`) for purpose correctness
  against the relevant spec, architecture/threading/lifetime, code-level
  correctness, and tests — writing a structured review document to
  `~/firefox-patches-review/`. Delegates to a new Opus **`firefox-review`** agent
  that reuses the toolkit's `spec-check`, `source-links`, and `gecko-navigator`.
- **`/review-dashboard` — open Revue, the human-review UI.** Resolves which git
  repo to review (the skill argument, else the current repo) and launches
  [Revue](https://github.com/alastor0325/revue) — a local web dashboard for
  reviewing a patch series by hand and generating a review prompt to hand back to
  Claude. Revue is an **optional** dependency, installed lazily (from GitHub) and
  consent-gated on first use; `/review` itself needs nothing extra.

## [0.2.8] — 2026-06-04

### Fixed
- **`/triage` no longer re-needinfos a bug it's already awaiting.** A
  recently-filed bug we already needinfo'd in a prior round also re-appears in
  the 14-day `fetch`, and the fetch path would draft a duplicate §1a needs-info —
  pulling an Awaiting bug back into NeedInfos and re-pinging the reporter (bug
  2043826: NI set 06-02, re-drafted 06-04). New pre-flight skip condition checks
  `ni-watch.json`: if the bug has an active NI on the needed party with no
  substantive reply since (and isn't stale), it stays Awaiting — and any
  duplicate pending draft is dropped. The "are we still awaiting?" gate now
  applies to fetched bugs, not just `watch-poll` hits.

## [0.2.7] — 2026-06-04

### Documentation
- **Tutorial now documents bug triage.** A new "Bug triage" section covers
  `/triage` and `/triage-dashboard` — setup and environment variables
  (`TRIAGE_OWNER`, `TRIAGE_DIR`, `TRIAGE_COMPONENTS` with its eight default
  Audio/Video components, `FX_BUG_INVESTIGATION_DIR`), the end-to-end triage
  flow, what each dashboard tab means, and how the Process queue gates every
  Bugzilla write — with a screenshot rendered from synthetic, public-only data
  (and click/scroll zoom in the lightbox).
- **Expanded "Investigate a bug"** with the `/bug-start` flow, what the
  investigation report contains, the deep vs. shallow (`--triage-mode`) depths,
  and the standalone `/analyze-profile` and `/check-log` analyzers.
- **Generalized the prose** so it reads for any Firefox component (the deeper
  bundled know-how for A/V is still noted), and **reordered** the page so
  "All commands" follows "Quick start".
- **Linked every dependency** in the README and tutorial to its upstream repo.

## [0.2.6] — 2026-06-04

### Changed
- **Bump the pinned triage dashboard to v0.2.1.** Its queue-drain summary now
  ends every line with the bug's Bugzilla link (always for applied bugs) so you
  can one-click to verify the write.

## [0.2.5] — 2026-06-04

### Changed
- **Pin the triage dashboard to a release.** `/triage-dashboard` now targets a
  specific dashboard version (`v0.2.0`) and upgrades the managed venv to it when
  it's stale — previously a first install was never updated, so the dashboard
  could run arbitrarily old code. `/update` installs the same pinned version.
  Bumping the pin in the skill is how the toolkit rolls forward to newer
  dashboard releases.

### Added
- **`/triage` records attachment `content_type`.** Each `bug_context.attachments`
  entry now carries the Bugzilla MIME type, so the dashboard detects images and
  videos exactly — a screenshot attached with a descriptive, extension-less name
  still opens in the in-page preview.

## [0.2.4] — 2026-06-04

### Changed
- **Viewer title links to the repo.** The `· fx-bug-toolkit` part of the
  investigations viewer header is now a hyperlink to the GitHub repository
  (opens in a new tab), with a subtle hover underline.

## [0.2.3] — 2026-06-04

### Added
- **`/triage` component set is now configurable** via a new `$TRIAGE_COMPONENTS`
  env var (optional; unset = the default eight A/V components). The default list
  and override rules live in `skills/triage/components.md` — the single source of
  truth that drives the meta-bug search, the pre-flight scope filter, and
  `bugzilla-cli fetch` (now passed `--component` flags; the CLI no longer treats
  its hardcoded list as authoritative). On the **first run** the Setup check shows
  the default components and asks whether to keep or customize them, persisting
  only a customized set; every run prints the resolved set before fetching.
  (Requires `bugzilla-cli` ≥ the build that adds `fetch --component`.)

## [0.2.2] — 2026-06-04

### Changed
- **`/triage` no longer auto-CCs/needinfos the triage owner.** It used to always
  put `$TRIAGE_OWNER` in `cc_add` and set NI-on-owner for §1b. Now `cc_add`
  defaults empty and the owner's CC/NI is **opt-in per draft, default off** — the
  owner ticks the dashboard's new **"CC me" / "NI me"** checkboxes (which add/
  remove `$TRIAGE_OWNER` from `cc_add`/`ni_targets`). `$TRIAGE_OWNER` is still
  required so those toggles know whom to add. Reporter needinfos (§1a) are
  unaffected. (Dashboard side ships in firefox-triage-dashboard.)

## [0.2.1] — 2026-06-04

### Fixed
- **`/triage-dashboard` launch** — replaced the fragile `nohup … & ; sleep 1`
  start (which detached unreliably from the non-interactive tool shell and
  claimed "serving" before uvicorn had bound) with a cross-platform detached
  spawn (`start_new_session` / Windows `DETACHED_PROCESS`, like `serve.py`) plus
  a readiness poll that only reports success once the server actually answers.
  Found via a live smoke test of the lazy bootstrap.

## [0.2.0] — 2026-06-04

### Added
- **Triage workflow** — `/triage` (Firefox A/V weekly bug triage: completeness,
  duplicate detection, P/S, needinfo drafting, meta-bug blocking; parallel sweep
  of watched + recent bugs, writing reviewable drafts) and `/triage-apply-feedback`
  (internal — re-drafts from queue feedback). Ported from the maintainer's personal
  skills, generalized: the CC/needinfo target is configurable via `$TRIAGE_OWNER`,
  the investigation dir is `$FX_BUG_INVESTIGATION_DIR`, and personal-workflow
  machinery (cron, usage telemetry, a personal GitHub auto-push) was dropped.
  Triage needs [`bugzilla-cli`](https://github.com/alastor0325/bugzilla-cli) +
  `$TRIAGE_OWNER`; it is **not** part of `/init` (investigate-only use stays lean).
- **`/triage-dashboard`** — opens the [triage dashboard](https://github.com/alastor0325/firefox-triage-dashboard)
  (a web UI over the drafts + investigations) at `http://127.0.0.1:8765/`. It's a
  separate pip app installed **lazily** into a managed venv (`~/.fx-bug-toolkit/venv`)
  the first time it's needed — consent-gated, so investigate-only users never pull
  the FastAPI stack. `/triage` opens it at the end of a full session; `/update`
  refreshes it when present.

## [0.1.5] — 2026-06-04

### Changed
- **`profiler-cli` (and `node`/`npm`) are now REQUIRED, not optional.** `init`
  treats `profiler-cli` as part of the core set and installs it — along with its
  headless **Playwright Firefox** browser (`npx playwright install firefox`) — so
  `/analyze-profile` works out of the box. `init`'s verdict is now **"Setup
  complete"** (was "Core investigation ready"), and any required item left
  uninstalled is reported as incomplete. README's dependency table marks the core
  tools required and notes the browser download.

## [0.1.4] — 2026-06-04

### Fixed
- **Skills silently misrouted when env vars were absent** (#8). Two visibility
  fixes so a missing/unpropagated env var is obvious instead of silent:
  - **Viewer launcher** now echoes the resolved `serve.py` (`Serving viewer
    from: …`) on success and a clear reason on failure — no more silent no-op.
  - **`bug-start`** announces the investigation directory **and its source**
    (`(from $FX_BUG_INVESTIGATION_DIR)` vs `(default — …not set in this shell)`)
    before writing, so a Windows User-level var the Bash shell can't see no
    longer silently splits investigations across two folders.
- **`init` env-var guidance** (#8): the "Windows / non-interactive PATH" recipe
  now also covers `FX_BUG_INVESTIGATION_DIR` / `WIKI_PATH` in the same `BASH_ENV`
  file (so non-interactive bash sees them regardless of Windows User-env
  propagation), warns that a **full terminal/OS relaunch** — not just a Claude
  Code restart — is needed for a new User var, and adds a step to **verify** the
  value is visible to the Bash tool.

## [0.1.3] — 2026-06-04

### Fixed
- **`/analyze-profile` crashed on first use** (#5): `init` now runs `npx
  playwright install firefox` after building `profiler-cli` (it drives a headless
  Playwright Firefox), and `update` re-asserts the browser on rebuild. Without it
  the first run died with `browserType.launch: Executable doesn't exist`.
- **`/browse` & `bug-start` viewer launcher failed on other machines** (#4):
  `${CLAUDE_PLUGIN_ROOT}` is neither substituted nor exported in skill Bash
  ([claude-code#9354](https://github.com/anthropics/claude-code/issues/9354)).
  The launcher now locates `serve.py` itself — via `CLAUDE_PLUGIN_ROOT` if set,
  else the plugin's `bin/` on `PATH`, else the plugin cache — using Python so it
  behaves identically in bash, zsh, and sh. No hardcoded maintainer path, and a
  clear message instead of `python: command not found` when only `python3` exists.
- **`update` masked failed CLI updates as "not installed"** (#6): replaced
  `cmd -v && install || echo "not installed"` with explicit `if`/`else`, so a
  failed `cargo install` now surfaces as a failure.

### Changed
- **`node --test tests/` → `node --test`** (#3): the directory positional is
  `require()`d as a module on Node ≥ 21 and the run fails before any test. The
  README, CI, dev-loop, and `test:logic` script now run `node --test` from the
  repo root (auto-discovers `tests/*.test.js`).
- **`spec-check` reads large specs reliably** (#7): Step 3 now points at the
  smallest section-scoped URL (e.g. the HTML Standard `multipage/` chapter +
  fragment) and names the exact algorithm in the WebFetch prompt, instead of
  fetching the multi-MB single-page spec that WebFetch truncates.

## [0.1.2] — 2026-06-04

### Fixed
- **Windows dependency detection** (#1): `init` no longer reports installed tools
  as MISSING when Claude Code's Bash tool (MSYS2) has a minimal PATH. Detection
  now falls back to canonical install dirs (`~/.cargo/bin`, `C:\Program Files\nodejs`,
  the npm global bin) and distinguishes **installed-but-off-PATH** from
  **missing**. Added a "Windows / non-interactive PATH" recipe (a `BASH_ENV`
  file) so the CLIs — and `profiler-cli`'s `.cmd` shim — actually resolve for
  skills; the README troubleshooting calls it out too.
- **Checklist A status convention** (#2): the `FX_BUG_INVESTIGATION_DIR` and
  `WIKI_PATH` rows now emit `✅` like every other item instead of a bare
  `key=value` line.

## [0.1.1] — 2026-06-04

### Fixed
- `/browse` and `bug-start`'s viewer auto-serve now reference the bundled
  `serve.py` via the inline-substituted `${CLAUDE_PLUGIN_ROOT}` instead of a
  hardcoded local path, so they work wherever the plugin is installed (previously
  fell back to a maintainer-specific `~/projects/...` path on other machines).

## [0.1.0] — 2026-06-04

First public release.

### Added
- **Investigation commands:** `/bug-start` (the hub — investigate a Firefox bug
  end to end), `/analyze-profile` (Firefox Profiler captures), `/check-log`
  (Firefox logs, media/EME/CDM-aware), `/init` (setup + dependency
  install/health check), `/update` (refresh the plugin + its CLIs).
- **Internal helpers** (Claude invokes these; not user commands):
  `update-investigation`, `spec-check`, `download-guard`, `source-links`, and
  the `gecko-navigator` agent.
- **`/browse` investigation viewer** — a local, single-page web UI over all your
  investigations: one-line summaries, folder tags, full-text search, deep-links
  (`#bug`), keyboard navigation, and a foldable sidebar. `bug-start` auto-serves
  it and deep-links to the bug it just investigated.
- **Offline-first data:** investigations are saved as plain Markdown on your
  machine (`FX_BUG_INVESTIGATION_DIR`, default `~/.fx-bug-toolkit/bug-investigation`);
  nothing is uploaded. Optional shared knowledge via the
  [firefox-wiki-plugin](https://github.com/alastor0325/firefox-wiki-plugin).
- **Cross-platform** (Windows / macOS / Linux) — Python launcher (`serve.py`),
  no bash-only scripts.
- **Tests + CI:** unit (indexer, viewer logic), integration (build/serve,
  `serve.py` launcher), plugin-structure contracts, and browser E2E (viewer +
  tutorial); GitHub Actions runs them on every push across all three OSes.
- **Getting-started tutorial** published via GitHub Pages.

[Unreleased]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.6.3...HEAD
[0.6.3]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.6.2...fx-bug-toolkit--v0.6.3
[0.6.2]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.6.1...fx-bug-toolkit--v0.6.2
[0.6.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.6.0...fx-bug-toolkit--v0.6.1
[0.6.0]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.5.1...fx-bug-toolkit--v0.6.0
[0.5.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.5.0...fx-bug-toolkit--v0.5.1
[0.5.0]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.10...fx-bug-toolkit--v0.5.0
[0.4.10]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.9...fx-bug-toolkit--v0.4.10
[0.4.9]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.8...fx-bug-toolkit--v0.4.9
[0.4.8]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.7...fx-bug-toolkit--v0.4.8
[0.4.7]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.6...fx-bug-toolkit--v0.4.7
[0.4.6]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.5...fx-bug-toolkit--v0.4.6
[0.4.5]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.4...fx-bug-toolkit--v0.4.5
[0.4.4]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.3...fx-bug-toolkit--v0.4.4
[0.4.3]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.2...fx-bug-toolkit--v0.4.3
[0.4.2]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.1...fx-bug-toolkit--v0.4.2
[0.4.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.4.0...fx-bug-toolkit--v0.4.1
[0.4.0]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.19...fx-bug-toolkit--v0.4.0
[0.3.19]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.18...fx-bug-toolkit--v0.3.19
[0.3.18]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.17...fx-bug-toolkit--v0.3.18
[0.3.17]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.16...fx-bug-toolkit--v0.3.17
[0.3.16]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.15...fx-bug-toolkit--v0.3.16
[0.3.15]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.14...fx-bug-toolkit--v0.3.15
[0.3.14]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.13...fx-bug-toolkit--v0.3.14
[0.3.13]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.12...fx-bug-toolkit--v0.3.13
[0.3.12]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.11...fx-bug-toolkit--v0.3.12
[0.3.11]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.10...fx-bug-toolkit--v0.3.11
[0.3.10]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.9...fx-bug-toolkit--v0.3.10
[0.3.9]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.8...fx-bug-toolkit--v0.3.9
[0.3.8]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.7...fx-bug-toolkit--v0.3.8
[0.3.7]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.6...fx-bug-toolkit--v0.3.7
[0.3.6]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.5...fx-bug-toolkit--v0.3.6
[0.3.5]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.4...fx-bug-toolkit--v0.3.5
[0.3.4]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.3...fx-bug-toolkit--v0.3.4
[0.3.3]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.2...fx-bug-toolkit--v0.3.3
[0.3.2]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.1...fx-bug-toolkit--v0.3.2
[0.3.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.0...fx-bug-toolkit--v0.3.1
[0.3.0]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.8...fx-bug-toolkit--v0.3.0
[0.2.8]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.7...fx-bug-toolkit--v0.2.8
[0.2.7]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.6...fx-bug-toolkit--v0.2.7
[0.2.6]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.5...fx-bug-toolkit--v0.2.6
[0.2.5]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.4...fx-bug-toolkit--v0.2.5
[0.2.4]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.3...fx-bug-toolkit--v0.2.4
[0.2.3]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.2...fx-bug-toolkit--v0.2.3
[0.2.2]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.1...fx-bug-toolkit--v0.2.2
[0.2.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.0...fx-bug-toolkit--v0.2.1
[0.2.0]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.5...fx-bug-toolkit--v0.2.0
[0.1.5]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.4...fx-bug-toolkit--v0.1.5
[0.1.4]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.3...fx-bug-toolkit--v0.1.4
[0.1.3]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.2...fx-bug-toolkit--v0.1.3
[0.1.2]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.1...fx-bug-toolkit--v0.1.2
[0.1.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.0...fx-bug-toolkit--v0.1.1
[0.1.0]: https://github.com/alastor0325/fx-bug-toolkit/releases/tag/fx-bug-toolkit--v0.1.0
