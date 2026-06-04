# Changelog

All notable changes to **fx-bug-toolkit** are documented here. The format
follows [Keep a Changelog](https://keepachangelog.com/), and the project uses
[semantic versioning](https://semver.org/). Each released version has a matching
`fx-bug-toolkit--vX.Y.Z` git tag.

## [Unreleased]

_Nothing user-facing yet._

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

[Unreleased]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.2...HEAD
[0.1.2]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.1...fx-bug-toolkit--v0.1.2
[0.1.1]: https://github.com/alastor0325/fx-bug-toolkit/compare/fx-bug-toolkit--v0.1.0...fx-bug-toolkit--v0.1.1
[0.1.0]: https://github.com/alastor0325/fx-bug-toolkit/releases/tag/fx-bug-toolkit--v0.1.0
