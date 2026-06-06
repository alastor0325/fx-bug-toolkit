# fx-bug-toolkit — TODO / outstanding work

Running list so we don't lose context between sessions. Newest decisions at the
top of each section. Check items off as they land.

---

## ✅ Decided: one plugin — no `fx-triage` spinoff

fx-bug-toolkit stays a single, unified plugin (investigate + triage + review);
the triage workflow is **not** being split into a separate `fx-triage` plugin. So
the old "plugin-②" / "cross-plugin" items are resolved as **leave-as-is** — they
were only conditional on a split that isn't happening:

- [x] **Dashboard aligned to `FX_BUG_INVESTIGATION_DIR`** — it reads
      `$FX_BUG_INVESTIGATION_DIR` (default `~/.fx-bug-toolkit/bug-investigation`),
      the same dir the toolkit uses; both halves look in the same place.
- [x] `bug-start`'s references to the **triage dashboard** (frontmatter / lock
      files it consumes) — **keep**; they're correct in one plugin.
- [x] `bug-start`'s references to **`/triage`** — **keep**.
- [x] `bug-start`'s **`--triage-mode`** path (§6.5) — **keep**; it's how `/triage`
      dispatches a fast investigation, same plugin.

(The triage **dashboard** stays a separate pip web-app, installed lazily and
version-pinned — that's a dependency, not a "plugin," and is unaffected.)

---

## 🟡 Dependency slimming & robustness (raised 2026-06-05)

- [x] **Let `/triage` run without an API key (read-only by default).** Done in
      fx-bug-toolkit 0.3.9 + `bugzilla-cli` v0.2.0. `bugzilla-cli` reads
      (`get`/`fetch`/`search`/`watch-poll`) now run anonymously when no key is set
      (public bugs only); `setup` asks read-only vs write mode; `/triage` defaults
      to read-only (no `$TRIAGE_OWNER`, no writes), auto-selects reply mode when a
      key is already configured, else asks. Writes (`apply`/`post-comment`/
      `set-ni`/`set-fields`) + `$TRIAGE_OWNER` are gated on reply mode.
      Still uses `bugzilla-cli` for reads (the binary is required; only the *key*
      is optional) — a fuller "no `bugzilla-cli` at all, read via `bmo-to-md`/`moz`
      MCP" path was not pursued.

- [x] **Made the dashboard read-only aware.** Done in `firefox-triage-dashboard`
      (unreleased on `main`, pending a version bump + pin sync): a live
      `reply_mode()` check (mirrors `bugzilla-cli`'s key detection) drives the UX —
      a "read-only · drafts only" badge, the per-card Apply becomes a disabled
      pill, the `/draft/{id}/apply` route is a no-op, and the Process-queue drain
      prompt skips the apply step (`prepare_queue_drain(reply_mode=False)`). The
      `/triage` Apply section guard + the `bugzilla-cli apply` backstop remain.
      (`triage-apply-feedback` needs nothing — it makes no Bugzilla writes.)
      **Follow-up when bumping:** tag the dashboard `vX.Y.Z` and bump its `REQUIRED`
      pin in `skills/triage-dashboard/SKILL.md` + `skills/update/SKILL.md`.

- [x] **Don't hardcode server ports — pick a free one and pass it.** Done across
      all three launchers: `/browse` (`serve.py` baaa586 — picks a free port,
      persists it in `.run/viewer.port` for reuse/status/URL) and
      `/triage-dashboard` + `/review-dashboard`→Revue (0f313f6 — skill picks a free
      port, passes `--port`, remembers it in `~/.fx-bug-toolkit/*.port` and reuses
      a still-answering instance, else picks a fresh one). `$PORT`/`FX_VIEWER_PORT`
      still force a port. Cross-platform (python3 free-port probe + git-bash POSIX
      tools). serve.py has unit tests for the pure port helpers.

- [ ] **`/update` doesn't refresh `bugzilla-cli`.** `/update` Step 2 updates
      `bmo-to-md`/`searchfox-cli`/`profiler-cli` + the triage dashboard, but never
      touches `bugzilla-cli` (installed only by `/triage`'s pinned hint). Add a
      step that installs/refreshes it at the manifest-pinned tag
      (`cargo install --git … --tag v<versions.json bugzilla-cli>`), and extend the
      drift test to cover that pin too.

- [x] **Dashboard read-only polish** (firefox-triage-dashboard, unreleased on
      `main` — ships when the dashboard is bumped + re-pinned): the will-apply diff
      is now labelled **"Proposed"** in read-only (`.diff--proposed`), which also
      reframes the `status: ASSIGNED` pill as a proposal rather than a plan.

- [ ] **`firefox-triage-dashboard` has no CI.** Unlike fx-bug-toolkit (full
      matrix + e2e in GitHub Actions), the dashboard repo has no CI workflow — its
      only gate is a local `pytest`. Add a GitHub Actions workflow (pytest, maybe
      across an OS matrix) so dashboard changes are verified like the toolkit's.

- [ ] **Manifest sync script (deferred).** Option 2 from the versions-manifest
      work: a `scripts/sync_versions.py` that rewrites the inline pins from
      `.claude-plugin/versions.json`. Skipped for now (only 2 pinned deps; the
      drift test already guarantees consistency). Revisit if the pinned-dep count
      grows.

---

## 🟢 Cross-platform polish (win/mac/linux)

Verified: the executable code (`build_index.py`, `serve.py`) is cross-platform,
and the viewer is browser-based. The launcher was bash; now `serve.py`
(per-OS detach/kill). Remaining is unix-worded *guidance*:
- [x] `init`: Windows install notes added — `rustup-init.exe`, `nvm-windows`,
      `%USERPROFILE%\.cargo\bin` on PATH.
- [x] Skill bash snippets (`command -v`, `~/`, `curl`, `||`) assume a POSIX
      shell — documented in the README **Platforms** note (Windows runs them under
      Claude Code's bundled git-bash). Also hardened `review-dashboard` to resolve
      `python3 || python` (was bare `python3`, which Windows git-bash lacks),
      matching the other skills.
- [x] ~~Optional: `serve.py` auto-open the browser per-OS.~~ Decided **no** — the
      launch *skills* open the URL per-OS (`open`/`xdg-open`/`start`); a detached
      background server shouldn't spawn a browser itself (flaky, and it'd open in
      the wrong session).

## 🟢 Toolkit polish (this plugin, when we get to it)

- [x] Moved the download-guard cache under the toolkit namespace:
      `~/.cache/firefox-download-guard` → **`~/.fx-bug-toolkit/download-cache`**
      (consistent with `FX_BUG_INVESTIGATION_DIR`). Updated `download-guard`,
      `bug-start`, `triage`, `init`, and the README. (The old cache, if present,
      is just orphaned transient files — no migration needed.)
- [ ] `history.log` now lives in the investigation dir (moved automatically with
      `FX_BUG_INVESTIGATION_DIR`) — confirm that's the desired home.
- [ ] Scripted, sanitized re-sync from `~/.claude/skills` → this repo (so future
      updates are "re-run + review diff", not manual copy). Plan Phase 1 item.
- [ ] `firefox-manager` skill is unidentified (empty description) — decide if it
      is relevant to anything here. Currently out of scope.

---

## 🧪 Verification still owed

- [ ] True clean-room install test (deferred — needs a container). Install
      Colima+Docker, start from bare `ubuntu`, run `/init`'s install commands
      (rustup → `cargo install bmo-to-md`/`searchfox-cli` → clone+build
      profiler-cli) to prove the installer works on a machine with nothing.
      ~3–5 GB, ~10 min, fully removable. Does NOT cover Claude-Code plugin
      loading (needs auth) — that part already verified live via `--plugin-dir`.
- [ ] Document how a coworker registers the `moz` MCP server (no auto-config;
      `init` reports on it but can't install it).

---

## ✅ Done

- Created the private repo + plugin scaffold (manifests, 9 skills, gecko-navigator agent).
- Sanitized personal references: removed the `auto-update-my-md` GitHub push,
  parametrized `profiler-cli` via `$PROFILER_CLI`, softened `/firefox-implementation`
  pointers, fixed the `/deep-dive` → `/spec-check` dangling command, and the
  `check-log` hardcoded `~/.claude/skills/...` Write-sandbox path.
- Added `init` (installs deps with confirmation + guides paths) and `update`
  (refreshes the plugin upstream + all CLI deps).
- Reframed the toolkit as general-purpose (A/V is the deepest-stocked domain, not a gate).
- Made the investigation dir configurable: `FX_BUG_INVESTIGATION_DIR`
  (default `~/.fx-bug-toolkit/bug-investigation`).
- Restructured `init` into two item-by-item checklists (env/paths + deps),
  REQUIRED vs OPTIONAL.
- `check-log`: kept the bundled `knowledge/*.md` as a read-only
  reference floor, converted §6 write-back to wiki-gated `/firefox-wiki:add`
  (else surface to user), made the skill read-only (dropped Write/Edit), and
  removed the personal `~/playready.txt` default log path.
- `check-log` §7 history log moved to the fixed namespaced path
  `~/.fx-bug-toolkit/log-analysis.log` (internal state — not user-configurable).
- Built the `/browse` investigation viewer (viewer.html + viewer.logic.js +
  build_index.py), deep-linkable, served via cross-platform `serve.py`.
- Test suite: `tests/` — Python (indexer unit + build/serve integration +
  plugin-structure contracts), Node (`viewer.logic` units), Playwright
  (`viewer.e2e.cjs` browser UI). Caught 5 real bugs during the review.
- Replaced bash `serve.sh` with cross-platform `serve.py` (win/mac/linux).
- Dev-flow: `/fx-bug-toolkit-dev` skill + root `CLAUDE.md` — tests must pass
  before committing. `init` got Windows install notes.
- Renamed `check-firefox-log` → `check-log`.
- Marked `spec-check`, `download-guard`, `source-links` as `user-invocable:
  false` (internal — Claude invokes them from other skills, hidden from the `/`
  menu). Confirmed via the Claude Code skills doc.
- Verified frontmatter on all 9 skills + the agent; live `--plugin-dir` load
  reports 9 skills + gecko-navigator.
