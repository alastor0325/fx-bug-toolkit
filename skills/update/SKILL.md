---
name: update
description: Update everything fx-bug-toolkit depends on — pull the plugin's own upstream changes (marketplace + plugin), refresh the firefox-wiki plugin if it's installed, and refresh the required CLIs (bmo-to-md, searchfox-cli, profiler-cli) to their latest versions, installing any that are missing. Triggers on "update fx-bug-toolkit", "update the toolkit", "fx-bug-toolkit update", "refresh dependencies".
allowed-tools: [Bash, Read, AskUserQuestion]
---

# fx-bug-toolkit — update

Refresh the plugin and all its dependencies to their latest versions. For the
**required** CLIs (`bmo-to-md`, `searchfox-cli`, `profiler-cli`) this also
**installs them when they're missing** — they're mandatory, so `/update` must not
leave a gap. It still needs the underlying toolchain present (`cargo` for the
Rust CLIs, `git`+`node`/`npm` for `profiler-cli`); if the toolchain itself is
missing, it stops and points you to `/init` (which installs Rust/Node, asking
first). **Optional** pieces — the triage dashboard, and Revue for
`/open-review` — are only refreshed when already installed; they stay
lazily installed on first use and are not pulled in here.

Run the steps, capture before/after versions where available, and print a
summary at the end.

## Step 1 — Update the plugin from upstream

The plugin ships from a git-backed marketplace. Refresh the marketplace from its
source, then update the plugin itself. A **Claude Code restart is required** to
apply a plugin update.

First record the **current version** (to report the bump at the end) — note the
`fx-bug-toolkit@fx-bug-toolkit` line:

```bash
claude plugin list | grep -A1 "fx-bug-toolkit@fx-bug-toolkit"   # remember this version as OLD
```

Then refresh and update:

```bash
claude plugin marketplace update fx-bug-toolkit            # refresh the marketplace from git
claude plugin update fx-bug-toolkit@fx-bug-toolkit         # update the plugin (restart to apply)
```

Use the **qualified `plugin@marketplace` name** (`fx-bug-toolkit@fx-bug-toolkit`)
— it matches how the toolkit is installed and how `claude plugin list` shows it.
The bare `claude plugin update fx-bug-toolkit` can fail to resolve, so don't rely
on it. (The `marketplace update` line above correctly takes the bare marketplace
name, `fx-bug-toolkit`.) Tell the user to **restart Claude Code** afterward so the
updated skills load.

### Also refresh the firefox-wiki plugin — only if it's installed

The optional [firefox-wiki](https://github.com/alastor0325/firefox-wiki-plugin)
plugin (the Accumulated Knowledge Database) is a **separate** Claude Code plugin.
If the user has it installed, refresh it the same way; if not, skip silently —
`/update` never installs it (that's a deliberate `/firefox-wiki:init` choice).

```bash
if claude plugin list 2>/dev/null | grep -q "firefox-wiki@firefox-wiki-plugin"; then
  claude plugin marketplace update firefox-wiki-plugin       # refresh its marketplace from git
  claude plugin update firefox-wiki@firefox-wiki-plugin      # update it (restart to apply)
  echo "✅ firefox-wiki plugin refreshed"
else
  echo "skip firefox-wiki (not installed — set it up with /firefox-wiki:init)"
fi
```

Like the toolkit, the wiki plugin pins its version, so this is a no-op until a new
version ships. The wiki **content** (your `$WIKI_PATH` repo) is separate — pull it
with normal `git` if you track a shared one; `/update` doesn't touch it.

## Step 2 — Update (and install-if-missing) the CLI dependencies

The **required** CLIs install when absent and upgrade when present; **optional**
pieces (triage dashboard) are only refreshed if already installed. Report each
outcome ("installed", "updated to <v>", "already current", or "skipped").

Surface failures as failures — don't use `command -v … && install || echo "…"`:
with `A && B || C`, a *failed* install (`B`) falls through to `C` and is
misreported as "not installed", masking a real failure.

### Required Rust CLIs — `bmo-to-md` + `searchfox-cli`

`cargo install` does everything in one shot: it **installs when absent**,
upgrades when a newer version/commit exists, and is a **no-op when already
current**. **Do not pass `--force`** — that rebuilds from source on every run
even when nothing changed (slow compiles for nothing); without it cargo still
picks up a newer crates.io release or git commit.

They need `cargo`. If `cargo` itself is missing, that's a toolchain gap `/update`
won't paper over — stop and point the user to `/init` (it installs Rust via
rustup, asking first):

```bash
if ! command -v cargo >/dev/null; then
  echo "⚠️  cargo not found — required to install bmo-to-md/searchfox-cli/bugzilla-cli. Run /init (installs Rust)."
else
  cargo install bmo-to-md \
    && echo "✅ bmo-to-md installed/updated" || echo "⚠️  bmo-to-md FAILED"
  cargo install searchfox-cli \
    && echo "✅ searchfox-cli installed/updated" || echo "⚠️  searchfox-cli FAILED"
  # bugzilla-cli (triage Bugzilla I/O) — refresh to the **pinned version** from
  # crates.io, but only if it's installed (it's a /triage tool, installed lazily on
  # first use, not part of the core set). Keep the version in sync with
  # `.claude-plugin/versions.json` (enforced by tests/test_plugin_structure.py).
  if command -v bugzilla-cli >/dev/null; then
    cargo install bugzilla-cli --version 0.2.0 \
      && echo "✅ bugzilla-cli installed/updated (v0.2.0)" || echo "⚠️  bugzilla-cli FAILED"
  else
    echo "skip bugzilla-cli (not installed — /triage installs it on first use)"
  fi
fi
```

**`profiler-cli`** (git pull; **rebuild only when the pull brought new commits**).
`profiler-cli` drives a headless Playwright **Firefox** to load the profiler SPA,
so re-assert the browser after a rebuild (Playwright versions can bump):
```bash
PDIR="${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}"
if [ -d "$PDIR/.git" ]; then
  before=$(git -C "$PDIR" rev-parse HEAD 2>/dev/null)
  if git -C "$PDIR" pull --ff-only; then
    after=$(git -C "$PDIR" rev-parse HEAD 2>/dev/null)
    if [ "$before" != "$after" ]; then
      ( cd "$PDIR" && npm install && npm run build && npx playwright install firefox ) \
        && echo "✅ profiler-cli rebuilt ($after)" \
        || echo "⚠️  profiler-cli rebuild FAILED — check $PDIR"
    else
      echo "profiler-cli already up to date ($after)"
    fi
  else
    echo "⚠️  profiler-cli git pull FAILED — check $PDIR"
  fi
elif command -v git >/dev/null && command -v npm >/dev/null; then
  echo "profiler-cli not present — installing (required)…"
  git clone https://github.com/dpalmeiro/profiler-cli "$PDIR" \
    && ( cd "$PDIR" && npm install && npm run build && npm link && npx playwright install firefox ) \
    && echo "✅ profiler-cli installed at $PDIR" \
    || echo "⚠️  profiler-cli install FAILED — check $PDIR"
else
  echo "⚠️  profiler-cli missing and needs git + node/npm to install — run /init"
fi
```

**triage dashboard** (only if it was lazily installed by `/open-triage`):
Install the version this plugin pins — keep `REQUIRED` in sync with
`skills/open-triage/SKILL.md`.
```bash
VENV="$HOME/.fx-bug-toolkit/venv"
BIN="$VENV/bin"; [ -d "$BIN" ] || BIN="$VENV/Scripts"
REQUIRED="0.5.0"
if [ -x "$BIN/pip" ]; then
  "$BIN/pip" install --quiet --upgrade "triage-dashboard==$REQUIRED" \
    && echo "✅ triage dashboard updated to v$REQUIRED" || echo "⚠️  triage dashboard update FAILED"
else
  echo "skip triage dashboard (not installed — /open-triage installs it on first use)"
fi
```

## Step 3 — Report, don't auto-update, the system tools

`node`, `python3`, `git`, and `mach` are managed outside this toolkit
(nvm/pyenv/system/your mozilla-central checkout). Just report their versions so
the user can update them deliberately if needed:
```bash
for t in node python3 git; do command -v "$t" >/dev/null && echo "$t $($t --version 2>&1 | head -1)"; done
```
`mach` updates with your Firefox checkout (`./mach`), and the `moz` MCP server is
updated wherever you registered it — neither is touched here.

## Step 4 — Summary

End every run with a short, concrete summary:

1. **Plugin version + what changed.** Compare the version recorded in Step 1
   (OLD) with the now-current one (NEW), and say what landed between them. Pull
   the canonical changelog rather than guessing:
   ```bash
   curl -fsS https://raw.githubusercontent.com/alastor0325/fx-bug-toolkit/main/CHANGELOG.md | head -80
   ```
   - The newest released `## [X.Y.Z]` heading is **NEW**.
   - If `NEW == OLD` → say "already on the latest (vNEW)".
   - Otherwise report `vOLD → vNEW`, and for each released version newer than
     OLD (skip `## [Unreleased]`) print one line: the version + the **bolded
     headline** of its entry. A few lines total — not the whole changelog.
2. **CLIs / dashboard.** One line each from Step 2: "updated to `<v>`", "already
   up to date", or "skipped (not installed)".
3. **Restart.** If the plugin version changed, remind the user to **restart
   Claude Code** — a plugin update does not apply to the running session.
