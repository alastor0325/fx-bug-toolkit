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

When `init` says **"Core investigation ready,"** you're good to go.

---

## Using it

The one command you'll use most — give it a **Bugzilla bug number**:

```
/bug-start 1899999
```

It investigates the bug end to end and writes an investigation file to
`~/.fx-bug-toolkit/bug-investigation/` (or wherever you point
`FX_BUG_INVESTIGATION_DIR` — see [Configuration](#configuration)).

You can also run the analyzers on their own:

```
/analyze-profile https://share.firefox.dev/xxxxxxxx
/check-log /path/to/firefox.log
```

…and revise an existing write-up:

```
/update-investigation
```

Tip: type `/` and start typing a name to see these in the picker, with the
source plugin shown next to each.

---

## What's inside

### Commands you can run

| Command | What it does |
|---|---|
| `/init` | One-time setup — checks your env + dependencies, offers to install what's missing |
| `/bug-start <bug-id>` | **The hub.** Investigate a Firefox bug end to end and write the investigation file |
| `/analyze-profile <url>` | Analyze a Firefox Profiler capture |
| `/check-log <path>` | Diagnose a Firefox log (great for media/EME/CDM crashes) |
| `/update-investigation` | Apply targeted edits to an investigation file |
| `/update` | Update the plugin + its CLI dependencies to the latest |

### Behind the scenes (Claude uses these automatically — you don't call them)

| Helper | What it does |
|---|---|
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
| `PROFILER_CLI` | `~/projects/profiler-cli/dist/index.js` | location of the profiler-cli binary |
| `WIKI_PATH` | `~/firefox-wiki` | location of the optional shared wiki |

> **Where to set them:** Claude Code runs skill commands in a **non-interactive**
> shell, so put any `export` in a file those shells read. For **zsh** that's
> `~/.zshenv` — **not** `~/.zshrc` (which only loads for interactive shells). For
> **bash**, a file sourced via `BASH_ENV`. If you set it in `.zshrc` only, the
> skills won't see it and will fall back to the default.

### Your data stays local and private

- **Investigation files** → `FX_BUG_INVESTIGATION_DIR` (never pushed anywhere)
- **Downloaded files** → `~/.cache/firefox-download-guard/` (temporary staging)

---

## Dependencies

`init` handles these for you — it detects what's missing and offers a one-tick
multi-select to install them. Here's the lay of the land:

| Tool | Needed for | Can `init` install it? |
|---|---|---|
| `bmo-to-md` | pulling Bugzilla content | yes |
| `searchfox-cli` | searching the codebase | yes |
| `profiler-cli` | `/analyze-profile` | yes |
| `cargo` (Rust) | building the two CLIs above | yes (via rustup) |
| `node` + `npm` | building profiler-cli | yes (via nvm) |
| `git`, `python3` | source links, helper scripts | guide-only (use your system) |
| `mach` + a mozilla-central checkout | local build / spec checks | guide-only (optional) |
| `moz` MCP server | Bugzilla/Phabricator MCP lookups | guide-only (optional) |
| `firefox-wiki` | knowledge accelerator | guide-only (optional) |

You can investigate bugs with just the **core** tools (`bmo-to-md`,
`searchfox-cli`, `git`, `python3`). The rest unlock extra features.

---

## Optional: the shared wiki

The separate **`firefox-wiki`** plugin makes investigations faster and smarter —
Claude checks known component behavior before reading code, and contributes new
findings back so the whole team benefits.

To use it: install the `firefox-wiki` plugin and clone its content to
`~/firefox-wiki` (or set `WIKI_PATH`). The toolkit detects it automatically and
works perfectly fine **without** it.

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
- **It's not using my custom `FX_BUG_INVESTIGATION_DIR`.** It's probably set in
  `~/.zshrc`; move it to `~/.zshenv` (see [Configuration](#configuration)).
- **`init` says `mach` is missing but I have a Firefox checkout.** That's
  expected — `mach` runs as `./mach` from your checkout, not as a global command.
  It's optional anyway.
