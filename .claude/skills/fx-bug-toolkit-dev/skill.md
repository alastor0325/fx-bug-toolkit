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

### Step 7 — Release (if the change ships to users)
If the change touches the **shipped** plugin (`skills/`, `agents/`, `viewer/`,
or `.claude-plugin/`) and users should receive it, cut a release — see
**Releasing** below. (Contributor-only files — `.claude/`, `tests/`, `docs/`,
`CLAUDE.md`, `tutorial/` — don't ship, so they don't need a version bump.)

### Step 8 — Conclude
Summarize: what changed, which tests were added/updated and that they pass,
whether the README/tutorial were updated, whether `/sync-tutorial` ran, and the
new version if you released.

---

## Releasing

This plugin **pins `version`** in `.claude-plugin/plugin.json`, so `claude plugin
update` compares the version *string* — **users only receive changes when the
version is bumped.** Pushing commits without a bump is a no-op for installed
users.

To publish a shippable change:

1. **Bump `version`** in `.claude-plugin/plugin.json` (semver):
   - **patch** (`0.1.0 → 0.1.1`): bug fixes, small internal tweaks to shipped files
   - **minor** (`0.1.0 → 0.2.0`): a new command/skill or feature
   - **major** (`0.1.0 → 1.0.0`): breaking change (renamed/removed command, changed default/env-var)
2. **Commit** the bump (with the change, or as its own `release: vX.Y.Z` commit).
3. **Tag + push** (validates `plugin.json` ↔ marketplace entry agree):
   ```bash
   claude plugin tag --push -m "fx-bug-toolkit %s"
   ```
4. **(Optional) GitHub release** for a changelog:
   ```bash
   gh release create fx-bug-toolkit--vX.Y.Z --title vX.Y.Z --notes "…"
   ```

Users then update with `/update` (or `claude plugin update fx-bug-toolkit`) and
restart Claude Code.
