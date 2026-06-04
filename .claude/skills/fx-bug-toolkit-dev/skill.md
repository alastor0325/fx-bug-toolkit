# fx-bug-toolkit Dev Loop

Mandatory workflow for all changes to this plugin. All steps are required and
cannot be skipped. This guidance is for **contributors working in this repo** —
it is not a shipped plugin skill.

## What kind of change is this?

- **Code** — `viewer/build_index.py`, `viewer/serve.py`, `viewer/viewer.html`,
  `viewer/viewer.logic.js`. Has real logic → must be tested.
- **Skill / manifest** — `skills/**/SKILL.md`, `agents/*.md`,
  `.claude-plugin/*.json`. Prompt text + structure → structurally tested.

## Core Requirements

- **DOM-free / pure logic must be extracted so it can be unit-tested.** Viewer
  logic goes in `viewer/viewer.logic.js` (not inline in `viewer.html`); Python
  logic goes in named functions in `build_index.py` (no I/O in the function).
- **Every function added or changed needs a unit test** covering its branches.
  Removed behavior gets a regression test asserting it stays removed.
- **The test suite must pass before committing** — failing tests are a hard
  blocker; fix them, never work around. See Step 3 for the commands.
- **README.md must be updated** when a command/skill is added or removed, or a
  flag/default/env-var changes.
- **No personal data** in shipped files: no personal GitHub URLs, no machine
  paths (use `$FX_BUG_INVESTIGATION_DIR` / `~`-relative / `CLAUDE_PLUGIN_ROOT`),
  and `viewer/index.json` must stay git-ignored (it contains private content).
- **Cross-platform**: code must run on Windows/macOS/Linux (no bash-only
  launchers — use Python; use `pathlib`, `as_posix()`, per-OS branches).

## Process

### Step 1 — Understand
Read the files involved and the tests that already cover them (`tests/README.md`
maps each suite). Know what's pure vs. DOM/I/O before touching anything.

### Step 2 — Extract & Develop
Implement. Keep entry points thin (DOM wiring in `viewer.html`; `main()` in the
Python scripts) and put logic in pure functions you can test directly.

### Step 3 — Write Tests & run the suite
Add/adjust tests under `tests/`, then run — all must be green:

```bash
python3 -m unittest discover -s tests      # indexer units + build/serve integration + plugin structure
node --test tests/                          # viewer pure-logic units
```

If you changed **viewer DOM behavior** (rendering, selection, search, keyboard,
deep-link, fold), also run the browser E2E:

```bash
cd tests && npm install && npx playwright install chromium   # first time only
node tests/viewer.e2e.cjs
```

If you changed a **skill or manifest**, `test_plugin_structure.py` (part of the
Python suite) must still pass — it checks frontmatter, `folder == name`, and the
invocable-vs-internal contract.

### Step 4 — Agent Review
Run `/simplify` (or `/code-review`) on the diff and apply the fixes.

### Step 5 — Commit & Push
```bash
git commit -m "<type>: <what and why>"
git push
```
Both are required. Never commit without pushing.

### Step 6 — Sync the tutorial
If this task changed the **viewer** (`viewer.html` / `viewer.logic.js`) or
anything the tutorial shows, run **`/sync-tutorial`** to regenerate the embedded
screenshot and re-verify the tutorial page before concluding. Don't let the
tutorial drift from the product.

### Step 7 — Conclude
Summarize: what changed, which tests were added/updated and that they pass,
whether the README/tutorial were updated, and whether `/sync-tutorial` ran.
