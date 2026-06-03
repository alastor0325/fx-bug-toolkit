---
name: init
description: One-time setup for the fx-bug-toolkit plugin — creates the data directories it writes to, and checks for the external CLIs/services each skill needs (reporting which feature degrades without each). Triggers on "init fx-bug-toolkit", "set up the toolkit", "fx-bug-toolkit setup".
allowed-tools: [Bash, Read, AskUserQuestion]
---

# fx-bug-toolkit — setup / health check

Run this once on a new machine. It is **idempotent** — safe to re-run any time
to re-check the environment. It only *creates data directories* and *reports*
on dependencies; it never installs system packages without asking.

## Step 1 — Create the data directories

These are the per-user locations the toolkit reads and writes. They are local
and private (investigations never leave the machine).

```bash
mkdir -p ~/firefox-bug-investigation
mkdir -p ~/.cache/firefox-download-guard
echo "data dirs ready:"
ls -d ~/firefox-bug-investigation ~/.cache/firefox-download-guard
```

## Step 2 — Check the external dependencies

For each, report ✅ found (with version/path) or ⚠️ missing, and **which
feature degrades** if absent. Do NOT fail the whole setup on a missing optional
dep — just report it.

```bash
check() { command -v "$1" >/dev/null 2>&1 && echo "✅ $1 — $(command -v "$1")" || echo "⚠️  $1 — MISSING ($2)"; }

# Required for core investigation
check bmo-to-md        "can't pull Bugzilla bug content — blocks most of bug-start"
check searchfox-cli    "no code search — bug-start / spec-check / gecko-navigator degrade"
check git              "source-links and local repo lookups degrade"
check python3          "minor helper scripts degrade"

# Feature-specific
check node             "profiler analysis can't run (analyze-profile)"
check mach             "no local build / spec checks against a checkout (spec-check, bug-start)"
```

### profiler-cli (drives `/analyze-profile`)

The location is `$PROFILER_CLI` (default `~/projects/profiler-cli/dist/index.js`).

```bash
PCLI="${PROFILER_CLI:-$HOME/projects/profiler-cli/dist/index.js}"
if [ -f "$PCLI" ]; then echo "✅ profiler-cli — $PCLI";
else echo "⚠️  profiler-cli MISSING at $PCLI — /analyze-profile won't run."
     echo "    Install it and either place it at the default path or set PROFILER_CLI."
fi
```

### moz MCP server (Bugzilla / Phabricator lookups)

`bug-start` uses `mcp__moz__get_bugzilla_bug`. There is **no auto-config** — the
coworker must register the `moz` MCP server in their Claude Code settings.
Report whether `mcp__moz__*` tools are available; if not, tell the user the
toolkit still works via `bmo-to-md`, but MCP-based lookups are unavailable.

## Step 3 — Optional: the shared wiki

The `firefox-wiki` plugin is an **optional accelerator**. The toolkit gates
every wiki touchpoint on this check and degrades silently when absent:

```bash
test -f "${WIKI_PATH:-$HOME/firefox-wiki}/INDEX.md" \
  && echo "✅ wiki installed at ${WIKI_PATH:-$HOME/firefox-wiki}" \
  || echo "ℹ️  wiki not installed — toolkit works without it (searches code directly)."
```

If the user wants it, point them to install the `firefox-wiki` plugin and clone
the wiki content to `~/firefox-wiki` (or set `WIKI_PATH`).

## Step 4 — Summary

Print a short table: each dependency, found/missing, and the degraded feature.
End with a one-line verdict: "Core investigation ready" if `bmo-to-md` +
`searchfox-cli` are present, else list what to install first.
