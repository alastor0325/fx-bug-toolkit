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
3. Walk **Checklist B — Dependencies** one item at a time (detection only).
4. **Install missing dependencies** via one multi-select prompt.
5. Print the final summary.

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
- [ ] **`WIKI_PATH`** — **OPTIONAL** (default `~/firefox-wiki`). Location of the
      optional shared wiki.
      ```bash
      echo "WIKI_PATH=${WIKI_PATH:-(unset → default ~/firefox-wiki)}"
      ```

---

## Checklist B — Dependencies (detect one by one — do NOT install yet)

Run each check and report `✅` / `⚠️ MISSING`. **Detection only here** — collect
the missing ones; installation happens in the next section as a single
selection. Each item is tagged **[installable]** (init can install it — offered
in the selection) or **[guide-only]** (init only points to instructions, never
auto-installs).

- [ ] **`cargo` (Rust toolchain)** — **REQUIRED**, **[installable via rustup]**.
      Builds `bmo-to-md` + `searchfox-cli`. Check: `command -v cargo`.
- [ ] **`bmo-to-md`** — **REQUIRED**, **[installable]** (needs cargo). Pulls
      Bugzilla bug content. Check: `command -v bmo-to-md`.
- [ ] **`searchfox-cli`** — **REQUIRED**, **[installable]** (needs cargo). Code
      search. Check: `command -v searchfox-cli`.
- [ ] **`git`** — **REQUIRED**, **[guide-only]**. Source links, repo lookups,
      cloning profiler-cli. Check: `command -v git`. If missing: system package
      manager / Xcode CLT.
- [ ] **`python3`** — **REQUIRED**, **[guide-only]**. Helper scripts. Check:
      `command -v python3`. If missing: pyenv / system package manager.
- [ ] **`node` + `npm`** — **[installable via nvm]**, needed for
      `/analyze-profile`. Check: `command -v node && command -v npm`.
- [ ] **`profiler-cli`** — **[installable]** (needs node/npm + git), powers
      `/analyze-profile`. Check: `command -v profiler-cli` (it's put on PATH via
      `npm link` during install).
- [ ] **`mach` + a mozilla-central checkout** — **OPTIONAL**, **[guide-only]**.
      Local build / spec checks. Check: `command -v mach`. If missing, guide:
      <https://firefox-source-docs.mozilla.org/setup/>. (It's a whole checkout,
      run as `./mach`, not a global binary — so this often shows missing even
      when you have a checkout.) Toolkit still works via searchfox.
- [ ] **`moz` MCP server** — **OPTIONAL**, **[guide-only]**. Bugzilla/Phabricator
      MCP lookups (`mcp__moz__*`). Check: `claude mcp list | grep -i moz`. No
      auto-config — guide the user to register it (`claude mcp add`). `bmo-to-md`
      covers the core Bugzilla path without it.
- [ ] **`firefox-wiki` plugin + content** — **OPTIONAL**, **[guide-only]**.
      Knowledge accelerator. Check:
      `test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md"`. If wanted: install
      the `firefox-wiki` plugin and clone its content to `~/firefox-wiki`.

---

## Install missing dependencies (one selection)

Collect every **[installable]** item that came back MISSING in Checklist B:
`cargo`, `node`+`npm`, `bmo-to-md`, `searchfox-cli`, `profiler-cli`.

- If none are missing → say "nothing to install" and go to the Summary.
- Otherwise present **one** `AskUserQuestion` with **`multiSelect: true`**
  listing each missing installable item (label + what it gates). The user ticks
  which to install; **selecting them in the question IS the install consent.**
  They may pick none. Guide-only items (`git`, `python3`, `mach`, `moz` MCP,
  `firefox-wiki`) are **never** in this list.

Then install **only the selected** items, in this dependency order (skip
unselected ones):

1. **rustup** (if `cargo` selected):
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
   source "$HOME/.cargo/env"
   ```
2. **nvm + node** (if `node` selected):
   ```bash
   # check https://github.com/nvm-sh/nvm for the latest version tag
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
   export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"
   nvm install --lts
   ```
3. **cargo CLIs** (`bmo-to-md`, `searchfox-cli`, if selected) — require `cargo`
   present (pre-existing or just installed in step 1):
   ```bash
   cargo install --git https://github.com/padenot/bmo-to-md   # bmo-to-md
   cargo install searchfox-cli                                 # searchfox-cli
   ```
4. **profiler-cli** (if selected) — requires node/npm + git. Clone, build, then
   `npm link` so the `profiler-cli` command lands on `PATH` (next to `node`):
   ```bash
   git clone https://github.com/dpalmeiro/profiler-cli "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}"
   cd "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}" && npm install && npm run build && npm link
   command -v profiler-cli && echo "✅ profiler-cli on PATH" || echo "⚠️  not on PATH — ensure the npm global bin dir is on PATH"
   ```

**Ordering guard:** never run a step whose toolchain is absent. If the user
selected `bmo-to-md`/`searchfox-cli` but NOT `cargo` and cargo is missing — or
selected `profiler-cli` while node/npm is missing and unselected — skip that
install and tell them to also select (or first install) the toolchain. After
installing, re-run the affected checks and report the new status before the
Summary.

---

## Summary

Present the results as **five categories**, each rendered as its own table with
a **Purpose** column (`Item | Purpose | Req? | Status`). Show every checklist
item exactly once, in the group below. For Status use `✅`, `⚠️ <why>`, or
`using default <path>`.

1. **Shell environment** _(must be correct)_
   - `~/.cargo/bin` on `$PATH` — so the Rust CLIs resolve — REQUIRED
2. **Configurable locations** _(env vars)_
   - `FX_BUG_INVESTIGATION_DIR` — where investigation files are stored — OPTIONAL
   - `WIKI_PATH` — shared-wiki location — OPTIONAL
3. **Core CLIs** _(the toolkit's working tools)_
   - `bmo-to-md` — pull Bugzilla bug content — REQUIRED
   - `searchfox-cli` — search the Gecko codebase — REQUIRED
   - `profiler-cli` — powers `/analyze-profile` — REQUIRED for `/analyze-profile`
   - `git` — source links, repo lookups — REQUIRED
   - `python3` — helper scripts — REQUIRED
4. **Dependencies for the core CLIs** _(toolchains to install/build/run them)_ —
   use columns `Item | Serves | Req? | Status`
   - `cargo` (Rust) — builds `bmo-to-md`, `searchfox-cli` — REQUIRED
   - `node` + `npm` — build & run `profiler-cli` — REQUIRED for `/analyze-profile`
5. **Optional features**
   - `mach` + checkout — local build / spec checks — OPTIONAL
   - `moz` MCP server — Bugzilla/Phabricator MCP lookups — OPTIONAL
   - `firefox-wiki` — knowledge accelerator (compounds) — OPTIONAL

Then the verdict (two levels):

- **Core investigation ready** once these are ✅: `~/.cargo/bin` on PATH,
  `cargo`, `bmo-to-md`, `searchfox-cli`, `git`, `python3`.
- **Full toolkit ready** additionally needs `profiler-cli` + `node`/`npm` (which
  enable `/analyze-profile`).
- List any outstanding REQUIRED items in order so the user knows what to fix
  first, and note which OPTIONAL features are unavailable and what enables each.
