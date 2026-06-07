# Tests

Tests are split into two suites **by coupling**, not by language:

| Suite | Location | Scope |
|---|---|---|
| **Plugin + seam** | `tests/` (this dir) | plugin structure contracts and the **skill↔viewer seam** |
| **Viewer** | [`viewer/tests/`](../viewer/tests/) | the viewer component, in isolation — travels with `viewer/` |

The split mirrors how the plugin is packaged: a component owns its internal
tests; the top-level suite owns the *contracts between* components (the things
that break when a component moves or its interface drifts).

One Node package at the **repo root** (`package.json` + `node_modules`) serves
both suites, so `require("playwright")` resolves from either location.

## This suite (`tests/`)

| File | Kind | Covers |
|---|---|---|
| `test_plugin_structure.py` | contract | manifests parse; every SKILL.md has valid frontmatter; `folder == name`; invocable-vs-internal contract; agent frontmatter |
| `test_serve_locator.py` | contract (**seam**) | the inline Python locator embedded in `open-investigation`/`bug-start` that finds the shipped `viewer/serve.py` — via `$CLAUDE_PLUGIN_ROOT`, the plugin's `bin/` on `$PATH`, then the plugin cache |
| `tutorial.e2e.cjs` | e2e (browser) | the tutorial page: title, chapter links, repo + wiki links, TOC chapter→hash, scrollspy hash-sync, foldable TOC toggle, click-to-enlarge lightbox open/backdrop/Esc |

## Run (no extra installs)

```bash
# Plugin structure + serve-locator seam
python3 -m unittest discover -s tests

# Viewer indexer + build/serve integration (the other suite)
python3 -m unittest discover -s viewer/tests

# Viewer pure-logic units (node --test finds *.test.js recursively, anywhere)
node --test
```

(Requires `python3` with `pyyaml`, and `node` — both already toolkit deps.)

> `node --test` with no path argument auto-discovers `*.test.js` recursively.
> Don't pass a directory (`node --test tests/`) — on Node ≥ 21 the positional is
> treated as a module to `require()` and the run fails before any test executes.

## Run the browser E2E (optional — needs Playwright)

```bash
npm install                          # from the repo root
npx playwright install chromium
node tests/tutorial.e2e.cjs          # the tutorial-page E2E lives in this suite
```

The viewer browser E2E lives in the viewer suite — see
[`viewer/tests/README.md`](../viewer/tests/README.md).
