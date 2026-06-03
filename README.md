# fx-bug-toolkit

A Claude Code plugin for **investigating Firefox A/V bugs**. It bundles the
per-bug investigation cluster — diagnose a bug, analyze profiles and logs, check
spec conformance, navigate the Gecko codebase, and write up findings — behind a
single hub skill, `bug-start`.

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
| `init` | One-time setup + dependency health check |

## Install

Add this repo as a plugin marketplace in Claude Code, then enable the
`fx-bug-toolkit` plugin. After enabling, run the setup:

```
/init
```

`/init` creates the data directories and checks every dependency, reporting
which feature degrades if any are missing.

## Data the toolkit uses (all local & private)

- `~/firefox-bug-investigation/` — investigation files you write (never pushed)
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

`PROFILER_CLI` defaults to `~/projects/profiler-cli/dist/index.js`; set it to
relocate. `WIKI_PATH` defaults to `~/firefox-wiki`.

## Optional: shared wiki

Install the separate `firefox-wiki` plugin and clone its content to
`~/firefox-wiki` (or set `WIKI_PATH`) for faster starts and compounding
knowledge. The toolkit gates every wiki touchpoint on a presence check and works
fully without it.
