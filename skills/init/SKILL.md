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
- Process items **one by one, in order**. For each, report a single line:
  `✅ <item>` or `⚠️ <item> — <why> → <action>`. Every item ends with one of
  those — never a bare `key=value`.
- **REQUIRED** items must end ✅ before "core investigation ready". An
  **OPTIONAL** item that falls back to its default counts as ✅.
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

- [ ] **Shell can find the tool dirs** — **REQUIRED**. Skills call `bmo-to-md` /
      `searchfox-cli` / `profiler-cli` by name, so their install dirs must be on
      **this** shell's `PATH` (Claude Code runs commands non-interactively). On
      **Windows** the Bash tool (MSYS2/Git-bash) has a *minimal* PATH that omits
      these even when they're on the Windows User PATH — fix it via the
      [Windows / non-interactive PATH](#windows--non-interactive-path) recipe below.
      ```bash
      cb="$HOME/.cargo/bin"
      case ":$PATH:" in
        *":$cb:"*) echo "✅ ~/.cargo/bin on PATH";;
        *) [ -d "$cb" ] \
             && echo "⚠️  ~/.cargo/bin exists but is NOT on this shell's PATH → see the Windows / non-interactive PATH recipe" \
             || echo "ℹ️  ~/.cargo/bin not present yet (cargo not installed — Checklist B)";;
      esac
      ```
- [ ] **`FX_BUG_INVESTIGATION_DIR`** — **OPTIONAL** (default
      `~/.fx-bug-toolkit/bug-investigation`). Where investigation files are stored.
      ```bash
      if [ -n "${FX_BUG_INVESTIGATION_DIR:-}" ]; then
        echo "✅ FX_BUG_INVESTIGATION_DIR=$FX_BUG_INVESTIGATION_DIR"
      else
        echo "✅ FX_BUG_INVESTIGATION_DIR unset → using default ~/.fx-bug-toolkit/bug-investigation"
      fi
      ```
      To relocate, `export` it where **non-interactive** shells read it (see the
      PATH note below) — not an interactive-only startup file, or the skills
      won't see it.
- [ ] **`WIKI_PATH`** — **OPTIONAL** (default `~/firefox-wiki`). Location of the
      optional shared wiki.
      ```bash
      if [ -n "${WIKI_PATH:-}" ]; then
        echo "✅ WIKI_PATH=$WIKI_PATH"
      else
        echo "✅ WIKI_PATH unset → using default ~/firefox-wiki"
      fi
      ```

---

## Checklist B — Dependencies (detect, then install)

Run this **one** detection block, then read the per-line results. The `have`
resolver checks `$PATH` first, then the canonical install dirs — so an installed
tool that simply isn't on this shell's PATH (common on Windows MSYS2) is reported
as **installed-but-off-PATH**, not MISSING.

```bash
have() {  # echoes "PATH|<path>" or "OFFPATH|<path>", else returns 1
  local t="$1" p
  if p=$(command -v "$t" 2>/dev/null); then echo "PATH|$p"; return 0; fi
  for p in "$HOME/.cargo/bin/$t" "$HOME/.cargo/bin/$t.exe" \
           "/c/Program Files/nodejs/$t" "/c/Program Files/nodejs/$t.exe" "/c/Program Files/nodejs/$t.cmd" \
           "$HOME/AppData/Roaming/npm/$t.cmd"; do
    [ -f "$p" ] && { echo "OFFPATH|$p"; return 0; }
  done
  return 1
}
report() {  # report <label> <tool>
  local r
  if r=$(have "$2"); then
    if [ "${r%%|*}" = PATH ]; then echo "✅ $1 → ${r#*|}"
    else echo "⚠️  $1 installed but NOT on this shell's PATH → ${r#*|}  (see Windows / non-interactive PATH)"; fi
  else echo "⚠️  $1 MISSING"; fi
}
for t in cargo bmo-to-md searchfox-cli git node npm profiler-cli mach; do report "$t" "$t"; done
# python: python3 or python
if r=$(have python3) || r=$(have python); then echo "✅ python → ${r#*|}"; else echo "⚠️  python MISSING"; fi
# moz MCP + wiki (guide-only)
claude mcp list 2>/dev/null | grep -qi moz && echo "✅ moz MCP registered" || echo "ℹ️  moz MCP not registered (optional)"
test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" && echo "✅ firefox-wiki present" || echo "ℹ️  firefox-wiki not installed (optional)"
```

What each item is (req / how it's installed):

- **`cargo`** — REQUIRED, **[installable via rustup]**. Builds `bmo-to-md` + `searchfox-cli`.
- **`bmo-to-md`** — REQUIRED, **[installable]** (needs cargo). Pulls Bugzilla content.
- **`searchfox-cli`** — REQUIRED, **[installable]** (needs cargo). Code search.
- **`git`** — REQUIRED, **[guide-only]**. Source links, cloning profiler-cli.
- **`python`/`python3`** — REQUIRED, **[guide-only]**. Helper scripts + the viewer launcher.
- **`node` + `npm`** — **[installable via nvm]**, needed for `/analyze-profile`.
- **`profiler-cli`** — **[installable]** (needs node/npm + git), powers `/analyze-profile`.
- **`mach` + checkout** — OPTIONAL, **[guide-only]**. Local build / spec checks. Run as `./mach`
  from a mozilla-central checkout, so it's usually *not* a global binary; the toolkit works via
  searchfox without it. Guide: <https://firefox-source-docs.mozilla.org/setup/>.
- **`moz` MCP server** — OPTIONAL, **[guide-only]**. `mcp__moz__*` lookups; register with
  `claude mcp add`. `bmo-to-md` covers the core Bugzilla path without it.
- **`firefox-wiki` plugin + content** — OPTIONAL, **[guide-only]**. Knowledge accelerator.

> An **installed-but-off-PATH** result means the tool exists but this shell can't
> run it by name — skills will fail to invoke it. Fix the PATH (see below); do
> **not** reinstall.

---

## Install missing dependencies (one selection)

Collect every **[installable]** item that came back **MISSING** (not merely
off-PATH) in Checklist B: `cargo`, `node`+`npm`, `bmo-to-md`, `searchfox-cli`,
`profiler-cli`.

- If none are missing → say "nothing to install" and go to the Summary.
- Otherwise present **one** `AskUserQuestion` with **`multiSelect: true`**
  listing each missing installable item (label + what it gates). The user ticks
  which to install; **selecting them in the question IS the install consent.**
  They may pick none. Guide-only items (`git`, `python`, `mach`, `moz` MCP,
  `firefox-wiki`) are **never** in this list.

Then install **only the selected** items, in this dependency order:

1. **rustup** (if `cargo` selected):
   ```bash
   curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
   source "$HOME/.cargo/env"
   ```
   *Windows:* download and run `rustup-init.exe` from <https://rustup.rs>.
2. **nvm + node** (if `node` selected):
   ```bash
   # check https://github.com/nvm-sh/nvm for the latest version tag
   curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
   export NVM_DIR="$HOME/.nvm"; . "$NVM_DIR/nvm.sh"
   nvm install --lts
   ```
   *Windows:* use [nvm-windows](https://github.com/coreybutler/nvm-windows) or install Node from <https://nodejs.org>.
3. **cargo CLIs** (`bmo-to-md`, `searchfox-cli`, if selected) — require `cargo`:
   ```bash
   cargo install --git https://github.com/padenot/bmo-to-md   # bmo-to-md
   cargo install searchfox-cli                                 # searchfox-cli
   ```
4. **profiler-cli** (if selected) — requires node/npm + git. Clone, build,
   `npm link`, then install its headless browser. profiler-cli drives a headless
   Playwright **Firefox** to load the profiler SPA, so `npx playwright install
   firefox` is **required** — without it the *first* `/analyze-profile` run
   crashes with `browserType.launch: Executable doesn't exist … Please run: npx
   playwright install`:
   ```bash
   git clone https://github.com/dpalmeiro/profiler-cli "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}"
   cd "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}" \
     && npm install && npm run build && npm link \
     && npx playwright install firefox
   ```
   Verify with the `have` resolver from Checklist B (not bare `command -v`, which
   misses Windows' npm global bin): `report profiler-cli profiler-cli`.
   *Windows note:* `npm link` makes `profiler-cli.cmd` in the npm global bin; that
   shim runs `node`, so **`node` must also be on the bash PATH** for it to launch
   — the recipe below puts both there.

**Ordering guard:** never run a step whose toolchain is absent. If the user
selected `bmo-to-md`/`searchfox-cli` but cargo is missing-and-unselected — or
`profiler-cli` while node/npm is missing-and-unselected — skip it and tell them
to also select the toolchain. After installing, re-run the affected `report`
lines and show the new status.

---

## Windows / non-interactive PATH

Claude Code runs skill commands through a **non-interactive** shell. On Windows
that's usually MSYS2/Git-bash with a **minimal PATH** that omits `~/.cargo/bin`,
`C:\Program Files\nodejs`, and the npm global bin (`~/AppData/Roaming/npm`) —
even though those are on your Windows *User* PATH and work in cmd/PowerShell. So
the CLIs can be installed yet invisible to skills, and `profiler-cli`'s `.cmd`
shim itself needs `node` on PATH to run.

The **same gap hits the toolkit's config env vars**: a Windows *User*-level
`FX_BUG_INVESTIGATION_DIR` (or `WIKI_PATH`) is not seen by the Bash tool either,
so `bug-start` silently falls back to the default dir and your investigations end
up split across two folders. Fix both at once by putting the dirs **and** the
config vars in the file non-interactive bash reads:

1. Create `~/.fx-bug-toolkit.env.sh` — PATH plus any config vars you want the
   skills to honor:
   ```bash
   export PATH="$HOME/.cargo/bin:/c/Program Files/nodejs:$HOME/AppData/Roaming/npm:$PATH"
   # Optional — only if you relocate these from their defaults:
   export FX_BUG_INVESTIGATION_DIR="$HOME/firefox-bug-investigation"
   export WIKI_PATH="$HOME/firefox-wiki"
   ```
2. Point **`BASH_ENV`** at it (non-interactive bash sources `$BASH_ENV` on
   startup). Set it as a **Windows User environment variable** so Claude Code's
   Bash tool inherits it, e.g. `BASH_ENV=C:\Users\<you>\.fx-bug-toolkit.env.sh`.
3. **Fully relaunch** — on Windows, child shells inherit the environment block
   captured when the app's parent process started, so a new User-level var needs
   a complete terminal/OS relaunch, **not just a Claude Code restart**. Then
   re-run `/init`.
4. **Verify it propagated** (don't assume) — confirm the Bash tool actually sees
   the value, not just PowerShell:
   ```bash
   echo "BASH_ENV=$BASH_ENV"
   echo "FX_BUG_INVESTIGATION_DIR=${FX_BUG_INVESTIGATION_DIR:-<unset → default>}"
   ```
   If `FX_BUG_INVESTIGATION_DIR` is still `<unset>` here, the skills will use the
   default regardless of what PowerShell reports — the env file above is the fix.

**macOS / Linux:** the tool dirs are usually already on PATH. If you relocate a
config var or a CLI, set it in the file your *non-interactive* shell reads (for
zsh that's `~/.zshenv`; for bash, the file `BASH_ENV` points to) — not an
interactive-only rc file — then verify with the `echo` above.

---

## Summary

Present the results as **five categories**, each a table with a **Purpose**
column (`Item | Purpose | Req? | Status`). Show every checklist item once. For
Status use `✅`, `⚠️ <why>` (incl. "installed, off-PATH"), or "using default".

1. **Shell environment** _(must be correct)_
   - `~/.cargo/bin` (and node / npm dirs) reachable on this shell's PATH — REQUIRED
2. **Configurable locations** _(env vars)_
   - `FX_BUG_INVESTIGATION_DIR` — where investigation files are stored — OPTIONAL
   - `WIKI_PATH` — shared-wiki location — OPTIONAL
3. **Core CLIs** _(the toolkit's working tools)_
   - `bmo-to-md` — pull Bugzilla bug content — REQUIRED
   - `searchfox-cli` — search the Gecko codebase — REQUIRED
   - `profiler-cli` — powers `/analyze-profile` — REQUIRED for `/analyze-profile`
   - `git` — source links, repo lookups — REQUIRED
   - `python` — helper scripts + viewer launcher — REQUIRED
4. **Dependencies for the core CLIs** _(toolchains)_ — columns `Item | Serves | Req? | Status`
   - `cargo` (Rust) — builds `bmo-to-md`, `searchfox-cli` — REQUIRED
   - `node` + `npm` — build & run `profiler-cli` — REQUIRED for `/analyze-profile`
5. **Optional features**
   - `mach` + checkout — local build / spec checks — OPTIONAL
   - `moz` MCP server — Bugzilla/Phabricator MCP lookups — OPTIONAL
   - `firefox-wiki` — knowledge accelerator — OPTIONAL

Then the verdict:

- **Core investigation ready** once these resolve on PATH: `cargo`, `bmo-to-md`,
  `searchfox-cli`, `git`, `python`.
- **Full toolkit ready** additionally needs `profiler-cli` + `node`/`npm`.
- If anything is **installed-but-off-PATH**, point at the Windows /
  non-interactive PATH recipe — that's a PATH fix, not a reinstall. List any
  outstanding REQUIRED items in order, and which OPTIONAL features are unavailable.
