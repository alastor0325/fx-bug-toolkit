# Viewer tests

Tests for the investigation **viewer** component (`../`) — the indexer, the
`serve.py` launcher, the pure render logic, and the browser DOM behaviour. They
exercise the viewer in isolation and are co-located with it so they travel with
the component.

The skill↔viewer *seam* (how `open-investigation`/`bug-start` locate `serve.py`) is tested
in the plugin suite at [`tests/`](../../tests/README.md), not here.

The Node package (`playwright`) lives at the **repo root**, so the `.cjs` E2E
files resolve `require("playwright")` via Node's upward module search.

| File | Kind | Covers |
|---|---|---|
| `test_build_index.py` | unit + e2e | frontmatter parsing, `clean_md` (keeps identifier `_`), `card_label`, `preview` fallback chain, recursive scan, numeric vs slug ids, folders, exclusions, sort |
| `test_serve.py` | integration | builds the index + serves the real assets on an ephemeral port (every asset returns 200; served index is valid); plus `serve.py` start / status / restart / stop on a free port, isolated copy |
| `viewer.logic.test.js` | unit | `escapeHtml`, `sfUrl`, `bz`, `depthMeta`, chip builders, `matchesQuery`, `byDate` |
| `viewer.e2e.cjs` | e2e (browser) | every viewer feature: render + newest-first, result count, depth/complexity/folder chips, sparse rows, search + empty state + clear, sort toggle, click→detail (heading, root cause, bugzilla link, searchfox affected-file links, related-bug links, rendered markdown, links open new-tab), hash updates on select, deep-link by `#hash`, hashchange on open page, `/`+`Esc`, `s`/`w`/`j`/`k` nav, `b` + `\` + toggle-button fold |
| `viewer.serve.e2e.cjs` | e2e (browser) | the **shipped `serve.py`** builds the index from real `.md` frontmatter (via `build_index.py`) and serves it; a real browser loads the page and asserts render, search, clear, click→detail. Covers serve.py → build_index → HTTP → browser end-to-end (needs `python3`+`pyyaml`) |

The DOM-free logic lives in `../viewer.logic.js` so it can be unit-tested in Node
and reused by the page; the DOM wiring is covered by the browser E2E.

## Run

```bash
# units + build/serve integration (no extra installs; needs pyyaml)
python3 -m unittest discover -s viewer/tests

# pure-logic units (node --test finds *.test.js recursively, from the repo root)
node --test

# browser E2E (needs Playwright; install once from the repo root)
npm install && npx playwright install chromium
node viewer/tests/viewer.e2e.cjs          # DOM behaviour (assets via a test server)
node viewer/tests/viewer.serve.e2e.cjs    # full chain: real serve.py + build_index + browser
```
