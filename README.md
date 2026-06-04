# fx-bug-toolkit

A Claude Code plugin for **investigating Firefox bugs**. It bundles the per-bug
investigation cluster — diagnose a bug, analyze profiles and logs, check spec
conformance, navigate the Gecko codebase, and write up findings — behind a
single hub skill, `bug-start`.

The **mechanics are component-agnostic** — nothing here is gated to a particular
area, so it works for any Firefox bug. The bundled domain knowledge currently
runs deepest for **A/V / media** (the `check-firefox-log` knowledge pages,
codec-spec coverage in `spec-check`, and many media examples), simply because
that's where it grew up. Coverage for other components deepens the same way: by
adding component knowledge (wiki pages, analogous `check-firefox-log/knowledge/`
files), not by changing code.

This toolkit **investigates and diagnoses**; it does not implement or land
patches. The shared knowledge wiki is an *optional* accelerator, not a
requirement.

## What's inside

| Skill / agent | Purpose |
|---|---|
| `bug-start` | The hub — investigate a Firefox bug end to end |
| `analyze-profile` | Analyze a Firefox Profiler capture |
| `check-firefox-log` | Diagnose a Firefox log (media/EME/CDM-aware) |
| `spec-check` | Verify spec conformance (web + codec/format/protocol) |
| `update-investigation` | Apply targeted edits to an investigation file |
| `download-guard` | The single approval gate for downloading external files |
| `source-links` | Rule: hyperlink every source/spec reference |
| `gecko-navigator` (agent) | Orient in the Gecko codebase; trace flows |
| `init` | One-time setup + dependency install/health check |
| `update` | Update the plugin (upstream) and all CLI dependencies to latest |

## Install

Add this repo as a plugin marketplace in Claude Code, then enable the
`fx-bug-toolkit` plugin. After enabling, run the setup:

```
/init
```

`/init` creates the data directories and checks every dependency, reporting
which feature degrades if any are missing.

To stay current later, run `/update` — it pulls the plugin's own upstream
changes and refreshes the CLI dependencies to their latest versions (restart
Claude Code afterward if the plugin itself updated).

## Data the toolkit uses (all local & private)

- `$FX_BUG_INVESTIGATION_DIR` (default `~/.fx-bug-toolkit/bug-investigation/`) —
  investigation files you write (never pushed)
- `~/.cache/firefox-download-guard/` — transient download staging

## External dependencies

| Tool | Gates | Required? |
|---|---|---|
| `bmo-to-md` | pulling Bugzilla content | core |
| `searchfox-cli` | code search | core |
| `node` + profiler-cli (`$PROFILER_CLI`) | `/analyze-profile` | feature |
| `mach` + a mozilla-central checkout | local build / spec checks | feature |
| `moz` MCP server | Bugzilla/Phabricator MCP lookups | feature |
| `git`, `python3` | source links, helpers | core |

### Configuration (env vars)

| Var | Default | Controls |
|---|---|---|
| `FX_BUG_INVESTIGATION_DIR` | `~/.fx-bug-toolkit/bug-investigation` | where investigation files are stored |
| `PROFILER_CLI` | `~/projects/profiler-cli/dist/index.js` | profiler-cli binary location |
| `WIKI_PATH` | `~/firefox-wiki` | optional shared-wiki location |

All are optional — set any of them in your shell rc to relocate.

## Optional: shared wiki

Install the separate `firefox-wiki` plugin and clone its content to
`~/firefox-wiki` (or set `WIKI_PATH`) for faster starts and compounding
knowledge. The toolkit gates every wiki touchpoint on a presence check and works
fully without it.
