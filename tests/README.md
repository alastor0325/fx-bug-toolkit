# Tests

Covers the only executable code in the plugin — the investigation **viewer** and
its **indexer** (everything else is prompt text; its structure is checked too).

Cross-platform: the Python and Node suites use only the standard library and run
on macOS, Linux, and Windows. The browser E2E needs Playwright.

## Run (no extra installs)

```bash
# Python: indexer unit tests, end-to-end build, serve integration, plugin structure
python3 -m unittest discover -s tests

# Node: viewer pure-logic unit tests (run from the repo root)
node --test
```

(Requires `python3` with `pyyaml`, and `node` — both already toolkit deps.)

> `node --test` with no path argument auto-discovers `tests/*.test.js`. Don't
> pass a directory (`node --test tests/`) — on Node ≥ 21 the positional is
> treated as a module to `require()` and the run fails before any test executes.

## Run the browser E2E (optional — needs Playwright)

```bash
cd tests
npm install
npx playwright install chromium
node viewer.e2e.cjs
```

## What's covered

| Suite | File | Kind | Covers |
|---|---|---|---|
| Indexer | `test_build_index.py` | unit + e2e | frontmatter parsing, `clean_md` (keeps identifier `_`), `card_label`, `preview` fallback chain, recursive scan, numeric vs slug ids, folders, exclusions, sort |
| Serve (static) | `test_serve.py` | integration | builds the index + serves the real assets on an ephemeral port; every asset returns 200; served index is valid |
| Serve (launcher) | `test_serve.py` | integration | `serve.py` start / status / restart / stop end-to-end on a free port, isolated copy |
| Plugin structure | `test_plugin_structure.py` | contract | manifests parse; every SKILL.md has valid frontmatter; folder == `name`; invocable-vs-internal contract; agent frontmatter |
| Viewer logic | `viewer.logic.test.js` | unit | `escapeHtml`, `sfUrl`, `bz`, `depthMeta`, chip builders, `matchesQuery`, `byDate` |
| Viewer UI | `viewer.e2e.cjs` | e2e (browser) | every feature: render + newest-first, result count, depth/complexity/folder chips, sparse rows, search + empty state + clear, sort toggle, click→detail (heading, root cause, bugzilla link, searchfox affected-file links, related-bug links, rendered markdown, links open new-tab), hash updates on select, deep-link by `#hash`, hashchange on open page, `/`+`Esc`, `s`/`w`/`j`/`k` nav, `b` + `\` + toggle-button fold |
| Tutorial UI | `tutorial.e2e.cjs` | e2e (browser) | the tutorial page: display title, all chapter links, repo + wiki links, TOC chapter→hash, scrollspy hash-sync (bookmarkable), foldable TOC toggle (inside the rail), click-to-enlarge lightbox open/backdrop-close/Esc-close |

The DOM-free logic lives in `viewer/viewer.logic.js` so it can be unit-tested in
Node and reused by the page; the DOM wiring is covered by the browser E2E.
