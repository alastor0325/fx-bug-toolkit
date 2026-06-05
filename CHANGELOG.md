# Changelog

All notable changes to **fx-bug-toolkit** are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/). Each released version has a matching
`fx-bug-toolkit--vX.Y.Z` git tag.

## [Unreleased]

_Nothing user-facing yet._

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

[Unreleased]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.3.1...HEAD
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
