---
name: update
description: Update everything fx-bug-toolkit depends on — pull the plugin's own upstream changes (marketplace + plugin), and refresh the external CLIs (bmo-to-md, searchfox-cli, profiler-cli) to their latest versions. Triggers on "update fx-bug-toolkit", "update the toolkit", "fx-bug-toolkit update", "refresh dependencies".
allowed-tools: [Bash, Read, AskUserQuestion]
---

# fx-bug-toolkit — update

Refresh the plugin and all its dependencies to their latest versions. Unlike
`/init` (which *installs* what's missing, asking first), this **updates what is
already installed**. It only touches things that are present — if a dependency
isn't installed, skip it and note that `/init` installs it.

Run the steps, capture before/after versions where available, and print a
summary at the end.

## Step 1 — Update the plugin from upstream

The plugin ships from a git-backed marketplace. Refresh the marketplace from its
source, then update the plugin itself. A **Claude Code restart is required** to
apply a plugin update.

```bash
claude plugin marketplace update fx-bug-toolkit   # refresh the marketplace from git
claude plugin update fx-bug-toolkit               # update the plugin (restart to apply)
```

If the install used the `plugin@marketplace` form, use that name (e.g.
`fx-bug-toolkit@fx-bug-toolkit`). Confirm with `claude plugin list` if unsure.
Tell the user to **restart Claude Code** afterward so the updated skills load.

## Step 2 — Update the CLI dependencies

Only run each block if the tool is already installed (`command -v` succeeds).
Skip-and-note otherwise.

Use an explicit `if`/`else` for each — **not** `command -v … && install || echo
"not installed"`. With `A && B || C`, a *failed* install (`B`) falls through to
`C` and falsely reports the tool as "not installed", masking a real update
failure. Surface install failures as failures:

**`bmo-to-md`** (from git — re-pull and rebuild latest):
```bash
if command -v bmo-to-md >/dev/null; then
  cargo install --git https://github.com/padenot/bmo-to-md --force \
    || echo "⚠️  bmo-to-md update FAILED"
else
  echo "skip bmo-to-md (not installed — run /init)"
fi
```

**`searchfox-cli`** (from crates.io — latest published):
```bash
if command -v searchfox-cli >/dev/null; then
  cargo install searchfox-cli --force \
    || echo "⚠️  searchfox-cli update FAILED"
else
  echo "skip searchfox-cli (not installed — run /init)"
fi
```

**`profiler-cli`** (git pull + rebuild). `profiler-cli` drives a headless
Playwright **Firefox** to load the profiler SPA, so re-assert the browser is
installed after rebuilding (Playwright versions can bump):
```bash
PDIR="${PROFILER_CLI_DIR:-$HOME/projects/profiler-cli}"
if [ -d "$PDIR/.git" ]; then
  if git -C "$PDIR" pull --ff-only \
       && ( cd "$PDIR" && npm install && npm run build && npx playwright install firefox ); then
    echo "✅ profiler-cli rebuilt"
  else
    echo "⚠️  profiler-cli update FAILED — check $PDIR"
  fi
else
  echo "skip profiler-cli (not cloned at $PDIR — run /init)"
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

Print a table: each item → previous → now (or "up to date" / "skipped"), and a
reminder to **restart Claude Code** if the plugin itself was updated in Step 1.
