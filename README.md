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
| `/triage` | Firefox A/V weekly bug triage — sweep watched + recent bugs, write reviewable drafts |
| `/triage-dashboard` | Open the triage dashboard (web UI over the drafts); lazily installs it on first use |
| `/review <D-rev\|local\|diff>` | AI patch review — verifies purpose against the spec, checks architecture & code, writes a structured review doc |
| `/review-dashboard [repo]` | Open **Revue**, the local web UI for reviewing a repo's patches by hand; lazily installs it on first use |
| `/update` | Update the plugin + its CLI dependencies to the latest |

### Behind the scenes (Claude uses these automatically — you don't call them)

| Helper | What it does |
|---|---|
| `update-investigation` | Revises an investigation file (ask in plain language, or `bug-start` uses it) |
| `triage-apply-feedback` | Re-drafts a triage draft from your feedback (the dashboard's queue drain uses it) |
| `spec-check` | Checks spec conformance (web specs + codec/format/protocol) |
| `download-guard` | Asks before downloading any external file, into one safe folder |
| `source-links` | Makes sure every code/spec reference is a real, clickable link |
| `gecko-navigator` (agent) | Orients in the Gecko codebase and traces execution flows |
| `firefox-review` (agent) | The Opus reviewer `/review` delegates to — purpose/spec/architecture/code review |

These are marked `user-invocable: false`, so they stay out of your command
picker — `bug-start` and friends pull them in when needed.

> **Triage extras (only for `/triage`):** triage needs [`bugzilla-cli`](https://github.com/alastor0325/bugzilla-cli)
> for Bugzilla I/O and a `$TRIAGE_OWNER` — the triage owner's Bugzilla email. The
> owner is CC'd/needinfo'd on a draft only when they **opt in** via the dashboard's
> per-draft **"CC me" / "NI me"** checkboxes (**default off**); the skill no longer
> auto-adds the owner. `$TRIAGE_OWNER` is **required and has no default** — the first
> `/triage` run prompts you for it and persists your answer, so you never set it
> by hand. The **dashboard** is a separate web app installed **lazily**
> the first time you run `/triage` or `/triage-dashboard` (a one-time venv + pip
> bootstrap, asked for first) — `/init` and investigate-only use never pull it in.

---

## Configuration

Everything works out of the box. You only need these if you want to change where
things live:

| Variable | Default | What it controls |
|---|---|---|
| `FX_BUG_INVESTIGATION_DIR` | `~/.fx-bug-toolkit/bug-investigation` | where your investigation files are saved |
| `TRIAGE_OWNER` | _(none — required for `/triage`)_ | triage owner's Bugzilla email; CC'd/needinfo'd only when opted in per draft (dashboard "CC me"/"NI me", default off) |
| `TRIAGE_DIR` | `~/firefox-triage/` | where `/triage` writes its drafts, watch list, and log |
| `TRIAGE_COMPONENTS` | _(the default A/V set)_ | `;`-separated list of exact Bugzilla component names `/triage` covers; unset = the default eight (see [`skills/triage/components.md`](skills/triage/components.md)) |

(The optional shared wiki has its own `WIKI_PATH` setting — see
[Optional: the shared wiki](#optional-the-shared-wiki).)

> **`TRIAGE_OWNER` has no default.** The **first time you run `/triage`**, if
> it's unset the skill asks you for the Bugzilla email (defaulting to your own
> account) and persists it to `~/.fx-bug-toolkit.env.sh` so later runs reuse it.
> `/triage` will not proceed without one, since it CCs/needinfo's that address on
> every draft.

> **`TRIAGE_COMPONENTS` is optional.** The components `/triage` covers are
> defined in [`skills/triage/components.md`](skills/triage/components.md) — the
> single source of truth (the skill, the meta-bug search, and `bugzilla-cli
> fetch` all read from it; the CLI no longer hardcodes the set). On the **first
> run** the skill shows the default eight A/V components and asks whether to keep
> them or customize; keeping the default writes nothing (unset = default), and
> customizing persists a `;`-separated list. Every run prints the resolved set
> before fetching so it's always clear which components it's triaging.

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
| [`bmo-to-md`](https://github.com/padenot/bmo-to-md) | pulling Bugzilla content | **required** | yes |
| [`searchfox-cli`](https://github.com/padenot/searchfox-cli) | searching the codebase | **required** | yes |
| [`profiler-cli`](https://github.com/dpalmeiro/profiler-cli) (+ Playwright Firefox) | `/analyze-profile` | **required** | yes |
| [`cargo`](https://rustup.rs) (Rust) | building the two CLIs above | **required** | yes (via rustup) |
| [`node`](https://nodejs.org) + `npm` | building/running profiler-cli | **required** | yes (via nvm) |
| [`git`](https://git-scm.com), [`python3`](https://www.python.org) | source links, helper scripts | **required** | guide-only (use your system) |
| [`mach`](https://firefox-source-docs.mozilla.org/mach/) + a mozilla-central checkout | local build / spec checks | optional | guide-only |
| `moz` MCP server | Bugzilla/Phabricator MCP lookups | optional | guide-only |
| [`revue`](https://github.com/alastor0325/revue) | `/review-dashboard` (human patch review UI) | optional | yes (lazily, on first `/review-dashboard`) |
| [`firefox-wiki`](https://github.com/alastor0325/firefox-wiki-plugin) | knowledge accelerator | optional | guide-only |

All the tools above the divider are **required** — `init` isn't "complete" until
they're installed. `profiler-cli` is part of the core set; installing it also
pulls a headless **Playwright Firefox** browser (~tens of MB), which it drives to
read Firefox Profiler captures for `/analyze-profile`. Only `mach`, the `moz` MCP
server, `revue`, and the shared wiki are optional extras. `revue` powers
`/review-dashboard` and is installed lazily (from GitHub) the first time you open
the dashboard — `/review` (the AI reviewer) needs nothing extra.

---

## Optional: the shared wiki

The skills get smarter when paired with the separate
**[firefox-wiki-plugin](https://github.com/alastor0325/firefox-wiki-plugin)** — a
growing, shared knowledge base of Firefox component behavior, spec deviations, and
debugging patterns. When it's present, skills like `/bug-start`,
`/analyze-profile`, and `/check-log` **consult the wiki before reading code** and
**contribute new findings back** (via `/firefox-wiki:add`), so each investigation
makes the next one faster — for you and anyone sharing the wiki. This is how you
extend the toolkit's knowledge and sharpen the skills over time, without changing
the skills themselves.

It has two halves: the **plugin** (adds the `/firefox-wiki:*` commands) and its
**content** (a git repo of knowledge). Clone the content to `~/firefox-wiki`, or
keep it anywhere and point `WIKI_PATH` at it:

| Variable | Default | What it controls |
|---|---|---|
| `WIKI_PATH` | `~/firefox-wiki` | location of the shared-wiki content (optional — leave unset to use the default) |

Like the other toolkit variable, `export` it where **non-interactive** shells
read it — Claude Code runs skill commands non-interactively, so an
interactive-only startup file won't be seen.

**Entirely optional.** Every skill gates wiki access on a presence check
(`${WIKI_PATH:-~/firefox-wiki}/INDEX.md`): if the wiki is there it's used; if not,
the wiki steps are skipped silently — no setup, no errors, and `WIKI_PATH` is
never required. The toolkit works fully on its own.

---

## Keeping it up to date

```
/update
```

This pulls the plugin's latest changes and refreshes its CLI dependencies.
**Restart Claude Code** afterward if the plugin itself was updated.
