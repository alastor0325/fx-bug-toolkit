# Dev Rules

All changes to this plugin must follow the **fx-bug-toolkit Dev Loop** defined in
`.claude/skills/fx-bug-toolkit-dev/skill.md`. Run `/fx-bug-toolkit-dev` at the
start of every implementation task.

Non-negotiables (see the skill for the full loop):

- **Tests must pass before committing.** `python3 -m unittest discover -s tests`
  and `node --test tests/`; plus `node tests/viewer.e2e.cjs` when viewer DOM
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
