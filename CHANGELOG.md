# Changelog

All notable changes to **fx-bug-toolkit** are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/). Each released version has a matching
`fx-bug-toolkit--vX.Y.Z` git tag.

## [Unreleased]

_Nothing user-facing yet._

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

[Unreleased]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.1...HEAD
[0.2.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.2.0...fx-bug-toolkit--v0.2.1
[0.2.0]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.5...fx-bug-toolkit--v0.2.0
[0.1.5]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.4...fx-bug-toolkit--v0.1.5
[0.1.4]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.3...fx-bug-toolkit--v0.1.4
[0.1.3]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.2...fx-bug-toolkit--v0.1.3
[0.1.2]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.1...fx-bug-toolkit--v0.1.2
[0.1.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.0...fx-bug-toolkit--v0.1.1
[0.1.0]: https://github.com/alastor0325/fx-bug-toolkit/releases/tag/fx-bug-toolkit--v0.1.0
