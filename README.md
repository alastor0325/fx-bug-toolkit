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

`/bug-start <bug-id>` runs the whole investigation; `/open-investigation` opens
the viewer to search and re-read past ones. The **[Getting Started tutorial](https://alastor0325.github.io/fx-bug-toolkit/)**
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
| `/open-investigation` | Open a local web viewer to search & read all your past investigations |
| `/triage` | Firefox bug triage for a team's components (A/V by default, DOM Core via `TRIAGE_TEAM=dom-core`) — sweep watched + untriaged bugs, write reviewable drafts |
| `/open-triage` | Open the triage dashboard (web UI over the drafts); lazily installs it on first use |
| `/review <D-rev\|local\|diff>` | AI patch review — routes the patch to per-aspect reviewers (**always** spec, security/memory-safety, threading, code quality, tests; **plus** IPC, error-handling, API usage when relevant), adversarially verifies the serious findings, and writes a structured review doc |
| `/open-review [worktree]` | Open **Revue**, the local web UI for reviewing a repo's patches by hand, on the right worktree. Pass a worktree path or a Revue worktree name; with no argument it opens the worktree the session works in, else your remembered repo (Revue's `revue init` default in `~/.revue/config.json`). Revue ≥ 0.3.2 selects the worktree at the path it is given. Lazily installs Revue on first use. Every repo shares one Revue port, and the dashboard at `/` switches between them |
| `/open-team [team]` | Open the [firefox-review-stats](https://alastor0325.github.io/firefox-review-stats/) team dashboards (review-load distribution + a digest of what each component shipped). Opens the live site — landing page by default, or `playback`/`webrtc`/`gfx` when named. No install |
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
| `firefox-review-aspect` (agent) | A single-dimension reviewer (spec/security/threading/IPC/…) that `/review` fans out to, one per dimension; also runs the adversarial verify pass. `/review` itself orchestrates from the main session |
| `close-verifier` (agent) | Checks a closing `/triage` draft (DUPLICATE, INVALID, …) with a fresh context and tries to prove it wrong; spawned by `/triage`, not directly |

These are marked `user-invocable: false`, so they stay out of your command
picker — `bug-start` and friends pull them in when needed.

> **Triage extras (only for `/triage`):** triage needs [`bugzilla-cli`](https://github.com/alastor0325/bugzilla-cli)
> for Bugzilla I/O. It runs **read-only by default** — fetching and drafting every
> action with **no API key** (reads hit BMO's public API; security-restricted bugs
> aren't visible). To write back (post comments, set needinfo/fields), enable
> **reply mode**: configure a key via `bugzilla-cli setup`, which also unlocks the
> `apply` step. Reply mode also needs a `$TRIAGE_OWNER` (the triage owner's Bugzilla
> email) — CC'd/needinfo'd only when they **opt in** via the dashboard's per-draft
> **"CC me" / "NI me"** checkboxes (**default off**). If a key is already configured
> when you run `/triage`, it picks reply mode automatically; otherwise it asks (and
> defaults to read-only). The **dashboard** is a separate web app installed **lazily**
> the first time you run `/triage` or `/open-triage` (a one-time venv + pip
> bootstrap, asked for first) — `/init` and investigate-only use never pull it in.
The dashboard installs from PyPI (`pip install triage-dashboard==…`) — a normal
registry install, so it goes through without any extra setup.

---

## Configuration

Everything works out of the box. You only need these if you want to change where
things live:

| Variable | Default | What it controls |
|---|---|---|
| `FX_BUG_INVESTIGATION_DIR` | `~/.fx-bug-toolkit/bug-investigation` | where your investigation files are saved |
| `FX_REVIEW_DIR` | `~/.fx-bug-toolkit/patches-review` | where `/review` writes its review documents |
| `TRIAGE_OWNER` | _(none — required for `/triage` **reply mode** only)_ | triage owner's Bugzilla email; CC'd/needinfo'd only when opted in per draft (dashboard "CC me"/"NI me", default off). Not needed in read-only mode |
| `TRIAGE_DIR` | `~/firefox-triage/` | where `/triage` writes its drafts, watch list, and log |
| `TRIAGE_TEAM` | `av` | which team profile `/triage` uses: `av` (Audio/Video) or `dom-core` (see [`skills/triage/teams/`](skills/triage/teams/)) |
| `TRIAGE_COMPONENTS` | _(the team profile's set)_ | `;`-separated list of `Product::Component` (or bare component) names `/triage` covers; unset = the profile's default (see [`skills/triage/components.md`](skills/triage/components.md)) |
| `FX_BUG_TOOLKIT_MODE` | _(unset: local mode)_ | set to `hackbot` only in the Hackbot cloud container; see [Hackbot mode](#hackbot-mode) |

(The optional shared wiki has its own `WIKI_PATH` setting — see
[Optional: the shared wiki](#optional-the-shared-wiki).)

> **`TRIAGE_OWNER` has no default — and only `/triage` reply mode needs it.** In
> read-only mode (the default when no API key is configured) it isn't required.
> In reply mode, the **first run** with it unset asks you for the Bugzilla email
> (defaulting to your own account) and persists it to `~/.fx-bug-toolkit.env.sh`
> so later runs reuse it; reply mode won't proceed without one, since it
> CCs/needinfo's that address when writing.

> **`TRIAGE_TEAM` and `TRIAGE_COMPONENTS` are optional.** Each team profile in
> [`skills/triage/teams/`](skills/triage/teams/) defines its components, queue,
> per-bug workflow, severity standard, and comment rules. `av` (the default)
> triages recent A/V bugs and hands fixable ones to `/bug-start`; `dom-core`
> works BugBot's untriaged list (open defects with no severity and no pending
> needinfo) and drafts a severity plus at most one comment per bug. You can also
> pass BugBot's query link: `/triage https://mzl.la/…`. For bugs nobody has
> vetted (anyone can file or comment), run it locked:
> `python3 skills/triage/run_locked.py --team dom-core [--print "/triage …"]`.
> That starts Claude Code with `--restricted`, no MCP servers, a hook that
> allows only read-only tools, drafts that pass `validate_draft.py`, and fetches
> of public sites (no localhost or private network), plus the Bash sandbox.
> Attachments are read with `read_attachment.py`: text as escaped text, images
> after a magic-byte check, never archives or binaries. It is read-only and
> anonymous. A DOM Core draft that closes a bug needs a confirm from the
> `close-verifier` subagent, which rereads the bug with a fresh context and
> tries to prove the close wrong. Add `--browsers` to a `--print` run to load the testcases it saved
> in Firefox Nightly, Chrome Canary and Safari TP afterwards: `run_testcases.py`
> does that with no model in the loop (pages served from 127.0.0.1 under a CSP,
> a dead proxy for Firefox and Chrome, a fresh profile per page, crash and
> security bugs skipped), then a second locked pass adds the results to the
> drafts. It finds `geckodriver`/`chromedriver` on `PATH` or via
> `FX_TRIAGE_GECKODRIVER`/`FX_TRIAGE_CHROMEDRIVER`, and browsers at their usual
> paths or via `FX_TRIAGE_FIREFOX`/`FX_TRIAGE_CHROME`. Review the drafts with
> `/open-triage` afterwards. On the **first run** the
> skill shows the profile's components and asks whether to keep them or
> customize; keeping the default writes nothing (unset = default), and
> customizing persists a `;`-separated list (see
> [`skills/triage/components.md`](skills/triage/components.md)). Every run prints
> the team and resolved set before fetching.

> **Where to set them:** Claude Code runs skill commands in a **non-interactive**
> shell, so `export` the variable in a file those shells read — not only an
> interactive-only startup file. If it's set but the skills don't pick it up,
> that's usually why; confirm with `<your-shell> -c 'echo $FX_BUG_INVESTIGATION_DIR'`.

### Hackbot mode

The gecko-triage Hackbot agent runs `/analyze-profile`, `/check-log`,
`spec-check` and `/bug-start --triage-mode` unattended in a cloud container. That
container has no local developer tools, so the agent must set
`FX_BUG_TOOLKIT_MODE=hackbot` in its session environment.
Each of these four skills then follows a short **Hackbot mode** section at its
top:

- **Tools:** Bugzilla, Searchfox, hg history and attachments come from the
  container's MCP tools (`mcp__bugzilla__*`, `mcp__searchfox__*`,
  `mcp__mozilla_vcs__*`, `mcp__attachments__fetch_attachment`) or from Grep and
  Read on its source checkout. The skills do not call `bmo-to-md`,
  `searchfox-cli`, `jj`, `mach` or the gecko-navigator agent.
- **Skipped steps:** the wiki, history logs, the lock file, the viewer, the
  session rename, the link check, tool installs and updates, and every question
  to the user. Findings and open questions go into the answer.
- **Files:** `/bug-start` writes only its investigation file, to
  `$FX_BUG_INVESTIGATION_DIR` (under `/tmp`). `/check-log` accepts every log
  path that `fetch_attachment` returns, such as `.moz_log` files.

When the variable is unset (or has any other value), the skills behave exactly
as before. Do not set it on a developer machine.

### Your investigations are yours — offline and local

- **Every investigation is saved offline**, as plain Markdown on your own
  machine. Nothing is uploaded; you have full control — read, edit, move, delete,
  or version them however you like.
- **The location is configurable** via `FX_BUG_INVESTIGATION_DIR` (default
  `~/.fx-bug-toolkit/bug-investigation`) — point it at any folder, including an
  existing notes repo.
- **Downloaded files** go to `~/.fx-bug-toolkit/download-cache/` (temporary staging).
- **Optional shared knowledge:** connect to a team knowledge base (the Firefox
  wiki) via the [firefox-wiki-plugin](https://github.com/alastor0325/firefox-wiki-plugin)
  — see [below](#optional-the-shared-wiki). It's purely additive; the toolkit
  works fully offline without it.

---

## Dependencies

> **Platforms.** Works on **macOS, Linux, and Windows**. On Windows the skills
> run under Claude Code's bundled **git-bash**, where the POSIX tools they use
> (`curl`, `cat`, `seq`, …) and `python`/`python3` are available; the launchers
> (`serve.py`, the dashboards) are cross-platform.

`init` handles these for you — it detects what's missing and offers a one-tick
multi-select to install them. Here's the lay of the land:

| Tool | Needed for | Required? | Can `init` install it? |
|---|---|---|---|
| [`bmo-to-md`](https://github.com/padenot/bmo-to-md) | pulling Bugzilla content | **required** | yes |
| [`searchfox-cli`](https://github.com/padenot/searchfox-cli) | searching the codebase | **required** | yes |
| [`profiler-cli`](https://www.npmjs.com/package/@firefox-devtools/profiler-cli) | `/analyze-profile` | **required** | yes |
| [`cargo`](https://rustup.rs) (Rust) | building the two CLIs above | **required** | yes (via rustup) |
| [`node`](https://nodejs.org) ≥ 24 + `npm` | installing/running profiler-cli | **required** | yes (via nvm) |
| [`git`](https://git-scm.com), [`python3`](https://www.python.org) | source links, helper scripts | **required** | guide-only (use your system) |
| [`bugzilla-cli`](https://github.com/alastor0325/bugzilla-cli) | `/triage` Bugzilla I/O — reads need **no** API key; writes (reply mode) need one | **for `/triage`** | yes (on first `/triage`, pinned `v0.2.0`) |
| [`mach`](https://firefox-source-docs.mozilla.org/mach/) + a mozilla-central checkout | local build / spec checks | optional | guide-only |
| `moz` MCP server | Bugzilla/Phabricator MCP lookups | optional | guide-only |
| [`revue`](https://github.com/alastor0325/revue) | `/open-review` (human patch review UI) | optional | yes (lazily, on first `/open-review`) |
| [`firefox-wiki`](https://github.com/alastor0325/firefox-wiki-plugin) | knowledge accelerator | optional | guide-only |
| [`bmo-search`](https://crates.io/crates/bmo-search) | `/triage` with `TRIAGE_TEAM=dom-core`: duplicate search by function name | optional | guide-only (`cargo install bmo-search`) |
| [`webspec-index`](https://github.com/jnjaeschke/webspec-index) | `spec-check` reading WHATWG/W3C/TC39 sections — exact section, no truncation, plus anchor validation / cross-refs / WHATWG-PR previews; falls back to `WebFetch` if absent | optional | guide-only (`cargo install webspec-index`) |

All the tools above the divider are **required** — `init` isn't "complete" until
they're installed. `profiler-cli` is part of the core set; it is the Firefox
Profiler team's npm package `@firefox-devtools/profiler-cli`, which reads Firefox
Profiler captures for `/analyze-profile`. Only `mach`, the `moz` MCP
server, `revue`, `webspec-index`, and the shared wiki are optional extras. `revue`
powers `/open-review` and is installed lazily (from GitHub) the first time you open
the dashboard — `/review` (the AI reviewer) needs nothing extra. `webspec-index`
(`cargo install webspec-index`) makes `spec-check` read web specs from a local
index instead of `WebFetch`; install it manually if you want that — `spec-check`
falls back to `WebFetch` when it's absent.

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
