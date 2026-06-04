---
name: init
description: One-time setup for the fx-bug-toolkit plugin — creates the data directories it writes to, installs the external CLIs it depends on (with your confirmation), and guides you through the paths/env vars and the dependencies that can't be auto-installed. Triggers on "init fx-bug-toolkit", "set up the toolkit", "fx-bug-toolkit setup".
allowed-tools: [Bash, Read, AskUserQuestion]
---

# fx-bug-toolkit — setup / install

Run this once on a new machine. **Idempotent** — safe to re-run to re-check or
to install anything still missing. The flow is: create data dirs → detect what's
present → offer to install each missing piece (asking first) → guide the parts
that can't be auto-installed → confirm env/PATH.

**Never install software without confirming first.** For each missing
dependency, show the exact command and use AskUserQuestion (Yes/No) before
running it.

## Step 1 — Create the data directories (no confirmation needed)

Local, private; investigations never leave the machine. The investigation
directory is `$FX_BUG_INVESTIGATION_DIR` if the user has set it, otherwise the
default `~/.fx-bug-toolkit/bug-investigation/`.

```bash
INVDIR="${FX_BUG_INVESTIGATION_DIR:-$HOME/.fx-bug-toolkit/bug-investigation}"
mkdir -p "$INVDIR" ~/.cache/firefox-download-guard
ls -d "$INVDIR" ~/.cache/firefox-download-guard
```

If the user wants investigations somewhere other than the default, tell them to
set `FX_BUG_INVESTIGATION_DIR` in their shell rc (every skill reads it):
```bash
echo 'export FX_BUG_INVESTIGATION_DIR="$HOME/.fx-bug-toolkit/bug-investigation"  # adjust to taste'
```

## Step 2 — Detect what's already installed

```bash
report() { command -v "$1" >/dev/null 2>&1 && echo "✅ $1 ($(command -v "$1"))" || echo "⚠️  $1 MISSING"; }
for t in cargo node npm git python3 bmo-to-md searchfox-cli mach; do report "$t"; done
PCLI="${PROFILER_CLI:-$HOME/projects/profiler-cli/dist/index.js}"
[ -f "$PCLI" ] && echo "✅ profiler-cli ($PCLI)" || echo "⚠️  profiler-cli MISSING ($PCLI)"
```

## Step 3 — Installer prerequisites (toolchains)

The CLIs below are installed via Rust (`cargo`) and Node (`npm`). If those are
missing, guide the user first — do not attempt to install the toolchains
silently:

- **Rust/cargo** missing → point to <https://rustup.rs> (`curl --proto '=https'
  --tlsv1.2 -sSf https://sh.rustup.rs | sh`). Needed for `bmo-to-md` and
  `searchfox-cli`.
- **Node/npm** missing → recommend nvm (<https://github.com/nvm-sh/nvm>) then
  `nvm install --lts`. Needed to build `profiler-cli`.

## Step 4 — Install the CLI dependencies (confirm each)

For each MISSING tool, AskUserQuestion (Yes/No) showing the command, then run it.

**`bmo-to-md`** — pulls Bugzilla bug content (core; without it `bug-start` can't
fetch bugs):
```bash
cargo install --git https://github.com/padenot/bmo-to-md
```

**`searchfox-cli`** — code search (core; `bug-start` / `spec-check` /
`gecko-navigator` degrade without it):
```bash
cargo install searchfox-cli
```

After installing, ensure `~/.cargo/bin` is on `PATH`:
```bash
case ":$PATH:" in *":$HOME/.cargo/bin:"*) echo "PATH ok";; *) echo 'Add to your shell rc: export PATH="$HOME/.cargo/bin:$PATH"';; esac
```

## Step 5 — profiler-cli (drives `/analyze-profile`)

profiler-cli is public (<https://github.com/dpalmeiro/profiler-cli>). It's a
TypeScript/Node project built with `tsc` to `dist/index.js`. With the user's
confirmation (needs Node/npm from Step 3):
```bash
git clone https://github.com/dpalmeiro/profiler-cli "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}"
cd "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}" && npm install && npm run build
test -f dist/index.js && echo "✅ built dist/index.js" || echo "⚠️  build did not produce dist/index.js — check the repo README"
```
The default `PROFILER_CLI` is `~/projects/profiler-cli/dist/index.js`. If you
cloned elsewhere, set it in your shell rc:
```bash
echo 'export PROFILER_CLI="$HOME/projects/profiler-cli/dist/index.js"  # adjust if relocated'
```

## Step 6 — Can't be auto-installed (guide only)

- **`mach`** — comes with a mozilla-central checkout, not a package. If the user
  does Firefox dev they already have it; otherwise point to the Firefox build
  docs (<https://firefox-source-docs.mozilla.org/setup/>). `spec-check` and some
  `bug-start` steps degrade without a local checkout, but the toolkit still works
  via searchfox.
- **`moz` MCP server** (`mcp__moz__get_bugzilla_bug`, …) — must be registered in
  the user's Claude Code MCP settings; there is no auto-config. Ask the user to
  register their `moz` MCP server (e.g. via `claude mcp add`). Without it,
  Bugzilla/Phabricator MCP lookups are unavailable, but `bmo-to-md` covers the
  core Bugzilla path.

## Step 7 — Optional: the shared wiki

The `firefox-wiki` plugin is an optional accelerator. Toolkit gates every wiki
touchpoint on this and degrades silently when absent:
```bash
test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" \
  && echo "✅ wiki at ${WIKI_PATH:-$HOME/firefox-wiki}" \
  || echo "ℹ️  no wiki — toolkit works without it (searches code directly)."
```
If wanted: install the `firefox-wiki` plugin and clone its content to
`~/firefox-wiki` (or set `WIKI_PATH`).

## Step 8 — Summary

Print a table: each dependency → installed / still-missing → what it gates, and
any env var the user still needs to set (`PROFILER_CLI`, `WIKI_PATH`, the
`~/.cargo/bin` PATH entry). Verdict: **"Core investigation ready"** once
`bmo-to-md` + `searchfox-cli` resolve on `PATH`; otherwise list what to install
first.
