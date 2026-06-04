---
name: init
description: One-time setup for the fx-bug-toolkit plugin — walks two checklists (environment/paths, then dependencies) one item at a time, ensuring every REQUIRED item is set/installed and confirming OPTIONAL ones can fall back to a default. Creates the data dirs and installs missing CLIs with your confirmation. Triggers on "init fx-bug-toolkit", "set up the toolkit", "fx-bug-toolkit setup".
allowed-tools: [Bash, Read, AskUserQuestion]
---

# fx-bug-toolkit — setup / install

Run this once on a new machine. **Idempotent** — safe to re-run to re-check or
install anything still missing.

**How to run this skill:**
1. Create the data directories (below).
2. Walk **Checklist A — Environment & paths** one item at a time.
3. Walk **Checklist B — Dependencies** one item at a time.
4. Print the final summary.

**Rules while walking a checklist:**
- Process items **one by one, in order**. For each, run its check and report a
  single line: `✅ <item>` or `⚠️ <item> — <why> → <action>`.
- **REQUIRED** items must end ✅ before "core investigation ready". An
  **OPTIONAL** item that falls back to its default counts as ✅ (note the
  default); only mark it ⚠️ if a feature the user wants is unavailable.
- **Never install software without confirming first** — show the exact command
  and use AskUserQuestion (Yes/No) before running it.

## Data directories (no confirmation needed)

```bash
INVDIR="${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}"
mkdir -p "$INVDIR" ~/.cache/firefox-download-guard
ls -d "$INVDIR" ~/.cache/firefox-download-guard
```

---

## Checklist A — Environment & paths (walk one by one)

- [ ] **`~/.cargo/bin` on `$PATH`** — **REQUIRED** (the core CLIs `bmo-to-md` and
      `searchfox-cli` install there; if it's not on PATH they won't resolve).
      ```bash
      case ":$PATH:" in
        *":$HOME/.cargo/bin:"*) echo "✅ ~/.cargo/bin on PATH";;
        *) echo '⚠️  ~/.cargo/bin NOT on PATH → add to your shell rc: export PATH="$HOME/.cargo/bin:$PATH"';;
      esac
      ```
- [ ] **Node/npm on `$PATH`** — **REQUIRED for `/analyze-profile`** (building
      profiler-cli); otherwise optional.
      ```bash
      command -v node >/dev/null && command -v npm >/dev/null \
        && echo "✅ node $(node --version) / npm $(npm --version)" \
        || echo "⚠️  node/npm not on PATH → install via nvm (see Checklist B)"
      ```
- [ ] **`FX_BUG_INVESTIGATION_DIR`** — **OPTIONAL** (default
      `~/.fx-bug-toolkit/bug-investigation/`). Where investigation files are
      stored.
      ```bash
      echo "FX_BUG_INVESTIGATION_DIR=${FX_BUG_INVESTIGATION_DIR:-(unset → default ~/.fx-bug-toolkit/bug-investigation)}"
      ```
      If the user wants a different location, they must `export
      FX_BUG_INVESTIGATION_DIR` somewhere **non-interactive shells read** —
      Claude Code runs skill commands non-interactively. For **zsh** that is
      `~/.zshenv` (NOT `~/.zshrc`, which only loads for interactive shells); for
      **bash**, a file sourced for non-interactive shells (e.g. via `BASH_ENV`).
      Setting it only in `~/.zshrc`/`~/.bashrc` means the skills won't see it and
      will fall back to the default.
- [ ] **`PROFILER_CLI`** — **OPTIONAL** (default
      `~/projects/profiler-cli/dist/index.js`). Path to the profiler-cli binary.
      ```bash
      echo "PROFILER_CLI=${PROFILER_CLI:-(unset → default ~/projects/profiler-cli/dist/index.js)}"
      ```
      Set it only if profiler-cli is built somewhere other than the default.
- [ ] **`WIKI_PATH`** — **OPTIONAL** (default `~/firefox-wiki`). Location of the
      optional shared wiki.
      ```bash
      echo "WIKI_PATH=${WIKI_PATH:-(unset → default ~/firefox-wiki)}"
      ```

---

## Checklist B — Dependencies (walk one by one)

For each: run the check; if missing, show the install command and confirm
(Yes/No) before running. Mark REQUIRED vs OPTIONAL as noted.

- [ ] **`cargo` (Rust toolchain)** — **REQUIRED** (needed to install the two core
      CLIs below).
      Check: `command -v cargo`. If missing, guide (do not auto-run): install
      from <https://rustup.rs> — `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`.
- [ ] **`bmo-to-md`** — **REQUIRED** (pulls Bugzilla bug content; without it
      `bug-start` can't fetch bugs).
      Check: `command -v bmo-to-md`. Install (confirm first):
      ```bash
      cargo install --git https://github.com/padenot/bmo-to-md
      ```
- [ ] **`searchfox-cli`** — **REQUIRED** (code search; `bug-start` / `spec-check`
      / `gecko-navigator` degrade badly without it).
      Check: `command -v searchfox-cli`. Install (confirm first):
      ```bash
      cargo install searchfox-cli
      ```
- [ ] **`git`** — **REQUIRED** (source links, repo lookups). Check:
      `command -v git`. If missing: install via system package manager / Xcode CLT.
- [ ] **`python3`** — **REQUIRED** (helper scripts). Check: `command -v python3`.
      If missing: install via pyenv or system package manager.
- [ ] **`node` + `npm` (toolchain)** — **OPTIONAL** (feature: building
      profiler-cli for `/analyze-profile`). Check: `command -v node && command -v npm`.
      If missing, guide: install nvm (<https://github.com/nvm-sh/nvm>) then
      `nvm install --lts`.
- [ ] **`profiler-cli`** — **OPTIONAL** (feature: `/analyze-profile`). Public
      TypeScript/Node project built with `tsc` to `dist/index.js`.
      Check: `test -f "${PROFILER_CLI:-$HOME/projects/profiler-cli/dist/index.js}"`.
      Install (confirm first; needs node/npm):
      ```bash
      git clone https://github.com/dpalmeiro/profiler-cli "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}"
      cd "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}" && npm install && npm run build
      test -f dist/index.js && echo "✅ built dist/index.js" || echo "⚠️  build did not produce dist/index.js — check the repo README"
      ```
      If built outside the default path, set `PROFILER_CLI` (Checklist A).
- [ ] **`mach` + a mozilla-central checkout** — **OPTIONAL** (feature: local
      build / spec checks). Not a package — comes with a Firefox checkout. Check:
      `command -v mach`. If missing, guide:
      <https://firefox-source-docs.mozilla.org/setup/>. Toolkit still works via
      searchfox without it.
- [ ] **`moz` MCP server** (`mcp__moz__get_bugzilla_bug`, …) — **OPTIONAL**
      (feature: Bugzilla/Phabricator MCP lookups). **No auto-config.** Ask the
      user to register their `moz` MCP server in Claude Code (e.g. `claude mcp
      add`). Without it, `bmo-to-md` still covers the core Bugzilla path.
- [ ] **`firefox-wiki` plugin + content** — **OPTIONAL** (accelerator). Check:
      ```bash
      test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" \
        && echo "✅ wiki at ${WIKI_PATH:-$HOME/firefox-wiki}" \
        || echo "ℹ️  no wiki — toolkit works without it (searches code directly)."
      ```
      If wanted: install the `firefox-wiki` plugin and clone its content to
      `~/firefox-wiki` (or set `WIKI_PATH`).

---

## Summary

Print a table covering **every checklist item**: item → REQUIRED/OPTIONAL →
✅ / ⚠️ / using-default → action still needed. Then the verdict:

- **"Core investigation ready"** once all REQUIRED items are ✅ —
  `~/.cargo/bin` on PATH, `cargo`, `bmo-to-md`, `searchfox-cli`, `git`,
  `python3`.
- Otherwise, list the REQUIRED items still outstanding, in order, so the user
  knows exactly what to fix first.
- Note which OPTIONAL features are unavailable and what enables each.
