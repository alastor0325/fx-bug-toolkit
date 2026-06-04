# sync-tutorial

Keep the getting-started tutorial in step with the rest of the plugin. Run this
**after any task that changes what the tutorial shows** — especially the viewer
(`viewer/viewer.html`, `viewer/viewer.logic.js`) or the tutorial page itself —
so the embedded screenshot and the page stay accurate. This is contributor
tooling, not a shipped plugin skill.

Run this from inside the repo; set `ROOT` to its top level:
`ROOT="$(git rev-parse --show-toplevel)"`.

## Steps

1. **Ensure Playwright is available** (first time only):
   ```bash
   ( cd "$ROOT" && npm install && npx playwright install chromium )
   ```

2. **Regenerate the viewer screenshot** the tutorial embeds (driven against the
   *current* viewer + the real example investigation):
   ```bash
   NODE_PATH="$ROOT/node_modules" node "$ROOT/tutorial/shoot.cjs"
   ```

3. **Verify the tutorial page still works** (TOC, hash-sync, lightbox, links):
   ```bash
   node "$ROOT/tests/tutorial.e2e.cjs"
   ```

4. **Commit if anything changed** (the screenshot is the usual diff):
   ```bash
   git -C "$ROOT" add tutorial/ && \
   git -C "$ROOT" commit -m "docs: sync tutorial" && git -C "$ROOT" push
   ```

If Playwright/Node aren't available, skip silently and note it — the tutorial is
documentation, not a runtime dependency. If you changed viewer text/labels,
double-check the tutorial's prose still matches.
