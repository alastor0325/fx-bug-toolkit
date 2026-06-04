# fx-bug-toolkit

A Claude Code plugin that helps you investigate Firefox bugs — fast.

Point it at a bug and it pulls the Bugzilla report, searches the Gecko codebase,
reads profiles and logs, checks the spec, and writes up a clean, link-rich
investigation file for you. One command does the whole thing: **`bug-start`**.

It works for **any Firefox component** — the mechanics aren't tied to a
particular area. The bundled know-how currently runs deepest for **media / A/V**
(that's where it grew up), and it gets smarter for other areas as people add
knowledge to the shared wiki.

This toolkit **investigates and diagnoses** — it doesn't write or land patches.
Think of it as the "understand the bug" half of your workflow.

> **New here?** The **[Getting Started tutorial](https://alastor0325.github.io/fx-bug-toolkit/)** is the
> friendliest way in — install, your first investigation, and the viewer, with
> screenshots. (It's an interactive page; open it in a browser.) This README is
> the quick reference.

> **About the commands:** you can type the short name — `/init`, `/bug-start`,
> etc. — and Claude Code's command picker shows which plugin each one comes from,
> so you can pick the `fx-bug-toolkit` one. The fully-qualified form
> (`/fx-bug-toolkit:init`) always works too, if you'd rather be explicit (handy
> when a personal skill or another plugin shares the same name).

---

## Quick start

**1. Install the plugin** (no clone needed):

```bash
claude plugin marketplace add alastor0325/fx-bug-toolkit
claude plugin install fx-bug-toolkit@fx-bug-toolkit
```

Prefer a local copy to read or hack on? Clone first, then point the marketplace
at the folder:

```bash
git clone https://github.com/alastor0325/fx-bug-toolkit.git ~/fx-bug-toolkit
claude plugin marketplace add ~/fx-bug-toolkit
claude plugin install fx-bug-toolkit@fx-bug-toolkit
```

**2. Restart Claude Code** so the plugin loads. (Plugins are picked up at
startup.)

**3. Run the setup** — it checks your machine and offers to install anything
missing:

```
/init
```

When `init` says **"Setup complete,"** you're good to go.

---

## Using it

`/bug-start <bug-id>` runs the whole investigation; `/browse` opens the viewer to
search and re-read past ones. The **[Getting Started tutorial](https://alastor0325.github.io/fx-bug-toolkit/)**
walks through it with examples and screenshots — start there.

Tip: type `/` and start typing a name to see these in the picker, with the
source plugin shown next to each.

---

## Commands

### You can run these

| Command | What it does |
|---|---|
| `/init` | One-time setup — checks your env + dependencies, offers to install what's missing |
| `/bug-start <bug-id>` | **The hub.** Investigate a Firefox bug end to end and write the investigation file |
| `/analyze-profile <url>` | Analyze a Firefox Profiler capture |
| `/check-log <path>` | Diagnose a Firefox log (great for media/EME/CDM crashes) |
| `/browse` | Open a local web viewer to search & read all your past investigations |
| `/update` | Update the plugin + its CLI dependencies to the latest |

### Behind the scenes (Claude uses these automatically — you don't call them)

| Helper | What it does |
|---|---|
| `update-investigation` | Revises an investigation file (ask in plain language, or `bug-start` uses it) |
| `spec-check` | Checks spec conformance (web specs + codec/format/protocol) |
| `download-guard` | Asks before downloading any external file, into one safe folder |
| `source-links` | Makes sure every code/spec reference is a real, clickable link |
| `gecko-navigator` (agent) | Orients in the Gecko codebase and traces execution flows |

These are marked `user-invocable: false`, so they stay out of your command
picker — `bug-start` and friends pull them in when needed.

---

## Configuration

Everything works out of the box. You only need these if you want to change where
things live:

| Variable | Default | What it controls |
|---|---|---|
| `FX_BUG_INVESTIGATION_DIR` | `~/.fx-bug-toolkit/bug-investigation` | where your investigation files are saved |
| `WIKI_PATH` | `~/firefox-wiki` | location of the optional shared wiki |

> **Where to set them:** Claude Code runs skill commands in a **non-interactive**
> shell, so `export` the variable in a file those shells read — not only an
> interactive-only startup file. If it's set but the skills don't pick it up,
> that's usually why; confirm with `<your-shell> -c 'echo $FX_BUG_INVESTIGATION_DIR'`.

### Your investigations are yours — offline and local

- **Every investigation is saved offline**, as plain Markdown on your own
  machine. Nothing is uploaded; you have full control — read, edit, move, delete,
  or version them however you like.
- **The location is configurable** via `FX_BUG_INVESTIGATION_DIR` (default
  `~/.fx-bug-toolkit/bug-investigation`) — point it at any folder, including an
  existing notes repo.
- **Downloaded files** go to `~/.cache/firefox-download-guard/` (temporary staging).
- **Optional shared knowledge:** connect to a team knowledge base (the Firefox
  wiki) via the [firefox-wiki-plugin](https://github.com/alastor0325/firefox-wiki-plugin)
  — see [below](#optional-the-shared-wiki). It's purely additive; the toolkit
  works fully offline without it.

---

## Dependencies

`init` handles these for you — it detects what's missing and offers a one-tick
multi-select to install them. Here's the lay of the land:

| Tool | Needed for | Required? | Can `init` install it? |
|---|---|---|---|
| `bmo-to-md` | pulling Bugzilla content | **required** | yes |
| `searchfox-cli` | searching the codebase | **required** | yes |
| `profiler-cli` (+ Playwright Firefox) | `/analyze-profile` | **required** | yes |
| `cargo` (Rust) | building the two CLIs above | **required** | yes (via rustup) |
| `node` + `npm` | building/running profiler-cli | **required** | yes (via nvm) |
| `git`, `python3` | source links, helper scripts | **required** | guide-only (use your system) |
| `mach` + a mozilla-central checkout | local build / spec checks | optional | guide-only |
| `moz` MCP server | Bugzilla/Phabricator MCP lookups | optional | guide-only |
| `firefox-wiki` | knowledge accelerator | optional | guide-only |

All the tools above the divider are **required** — `init` isn't "complete" until
they're installed. `profiler-cli` is part of the core set; installing it also
pulls a headless **Playwright Firefox** browser (~tens of MB), which it drives to
read Firefox Profiler captures for `/analyze-profile`. Only `mach`, the `moz` MCP
server, and the shared wiki are optional extras.

---

## Optional: the shared wiki

The separate **[firefox-wiki-plugin](https://github.com/alastor0325/firefox-wiki-plugin)**
makes investigations faster and smarter — Claude checks known component behavior
before reading code, and contributes new findings back so the whole team benefits.

To use it: install the plugin and clone its content to `~/firefox-wiki` (or set
`WIKI_PATH`). The toolkit detects it automatically and works perfectly fine
**without** it.

---

## Keeping it up to date

```
/update
```

This pulls the plugin's latest changes and refreshes its CLI dependencies.
**Restart Claude Code** afterward if the plugin itself was updated.

---

## Troubleshooting

- **I don't see the commands after installing.** Restart Claude Code — plugins
  load at startup. Then type `/` and start typing a command name.
- **It's not using my custom `FX_BUG_INVESTIGATION_DIR`.** It's likely exported
  only in an interactive-only startup file; set it where non-interactive shells
  read it too — Claude Code runs commands non-interactively (see
  [Configuration](#configuration)).
- **`init` says `mach` is missing but I have a Firefox checkout.** That's
  expected — `mach` runs as `./mach` from your checkout, not as a global command.
  It's optional anyway.
- **`/analyze-profile` fails with `browserType.launch: Executable doesn't
  exist … Please run: npx playwright install`.** `profiler-cli` drives a headless
  Playwright Firefox; install it once with `npx playwright install firefox` (run
  in the `profiler-cli` directory) or just re-run `/init`, which now does this.
- **On Windows, `init` reports installed tools as MISSING** (cargo, node,
  bmo-to-md, …). Claude Code's Bash tool (MSYS2/Git-bash) uses a minimal PATH
  that omits `~/.cargo/bin`, `C:\Program Files\nodejs`, and the npm global bin —
  even though they're on your Windows PATH. Put them on the non-interactive bash
  PATH via a `BASH_ENV` file; `/init`'s **"Windows / non-interactive PATH"**
  section has the exact recipe. (This also lets `profiler-cli`'s `.cmd` shim find
  `node`.)

---

## Contributing

Code lives in `viewer/` (the indexer + the browse UI); the skills are in
`skills/`. Tests are in `tests/` — see [`tests/README.md`](tests/README.md). All
changes follow the **fx-bug-toolkit Dev Loop**
([`.claude/skills/fx-bug-toolkit-dev/skill.md`](.claude/skills/fx-bug-toolkit-dev/skill.md)):
extract pure logic, unit-test it, and run the suite before committing.

Releases are versioned (`plugin.json` + a `fx-bug-toolkit--vX.Y.Z` tag); see the
[changelog](CHANGELOG.md).
