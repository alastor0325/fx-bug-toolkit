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
