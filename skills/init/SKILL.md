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

Local, private; investigations never leave the machine.

```bash
mkdir -p ~/firefox-bug-investigation ~/.cache/firefox-download-guard
ls -d ~/firefox-bug-investigation ~/.cache/firefox-download-guard
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

⚠️ **Sharing note:** profiler-cli currently lives in a **private** repo
(`alastor0325/profiler-cli`). A coworker can only install it if it has been made
public or shared with them. If the user is the owner, confirm the repo URL they
want coworkers to use; otherwise treat `/analyze-profile` as unavailable and say
so. **Do not hardcode a private clone URL into a shared instruction without
checking access.**

If the user has access, with their confirmation:
```bash
# adjust the URL to whatever the user confirms is reachable
git clone <profiler-cli-repo-url> "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}"
cd "${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}" && npm install && npm run build
# verify dist/index.js exists; the build script may differ — check the repo README
```
Then set `PROFILER_CLI` if the binary isn't at the default
`~/projects/profiler-cli/dist/index.js`:
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
