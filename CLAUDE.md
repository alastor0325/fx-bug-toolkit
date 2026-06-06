# Dev Rules

All changes to this plugin must follow the **fx-bug-toolkit Dev Loop** defined in
`.claude/skills/fx-bug-toolkit-dev/skill.md`. Run `/fx-bug-toolkit-dev` at the
start of every implementation task.

Non-negotiables (see the skill for the full loop):

- **Tests must pass before committing.** Two Python suites —
  `python3 -m unittest discover -s tests` (plugin structure + serve-locator seam)
  and `python3 -m unittest discover -s viewer/tests` (viewer indexer/serve) —
  plus `node --test` (from the repo root — not `node --test tests/`, which fails
  on Node ≥ 21); plus `node viewer/tests/viewer.e2e.cjs` when viewer DOM
  behavior changed.
- **Extract pure logic so it's unit-testable** (`viewer/viewer.logic.js`;
  named functions in `build_index.py`). Every changed function gets a test.
- **No personal data / machine paths** in shipped files; keep
  `viewer/index.json` git-ignored.
- **Cross-platform** (Windows/macOS/Linux) — no bash-only launchers.
- **Update README.md** when a command/flag/default/env-var changes.
- **Sync the tutorial** after changing the viewer or anything it shows: run
  `/sync-tutorial` to regenerate the screenshot + re-verify the page, so the
  tutorial never drifts from the product.
- **Release to ship.** `version` in `.claude-plugin/plugin.json` is pinned, so
  `claude plugin update` is a no-op until it's bumped. When a change to the
  shipped plugin (`skills/`/`agents/`/`viewer/`/`.claude-plugin/`) should reach
  users, bump the semver version and `claude plugin tag --push` (see the dev
  loop's **Releasing** section). Contributor-only files don't need a bump.
- **Verify CI, never assume green.** CI runs the full suite across an OS matrix
  (incl. Windows) that local one-OS runs can't cover. After any push, watch the
  run to green; prefer a branch + PR merged only when green; tag a release only
  from a green `main` commit. (See the dev loop's Step 5 + Releasing.)
- **Capture TODOs in `docs/TODO.md`, not just chat.** Whenever a follow-up,
  known gap, deferred decision, or "we should also…" surfaces during any task —
  even mid-conversation — append it to `docs/TODO.md` under the right section
  (🔴/🟡/🟢/🧪) with a one-line context and the date, before concluding. Check
  items off (or move to **✅ Done**) when they land. A TODO that lives only in
  the conversation is lost at the end of the session.
