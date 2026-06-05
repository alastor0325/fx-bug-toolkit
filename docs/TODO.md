# fx-bug-toolkit — TODO / outstanding work

Running list so we don't lose context between sessions. Newest decisions at the
top of each section. Check items off as they land.

---

## 🔴 Cross-plugin (must do before fx-triage / the dashboard ships)

- [ ] **Align the dashboard to `FX_BUG_INVESTIGATION_DIR`.** Plugin ② (the
      `firefox-triage-dashboard` repo) still reads `FIREFOX_INVESTIGATION_DIR`
      with default `~/firefox-bug-investigation`. This toolkit now uses
      `FX_BUG_INVESTIGATION_DIR` with default `~/.fx-bug-toolkit/bug-investigation`.
      Until the dashboard is updated, the two halves look in **different
      directories**. When packaging fx-triage: make the dashboard read
      `FX_BUG_INVESTIGATION_DIR` and adopt the same default.
      (Dashboard code today: `src/triage_dashboard/data.py` —
      `FIREFOX_INVESTIGATION_DIR` / `DEFAULT_INVESTIGATION_DIR`.)

---

## 🟡 Plugin-② coupling left inside bug-start (review when scoping fx-triage)

These are harmless for a standalone toolkit but reference things a toolkit-only
user won't have. Decide per item: leave (becomes correct once ② ships), soften,
or strip.

- [ ] ~8 "the triage dashboard …" references in `bug-start` (explain how its
      output frontmatter — `depth: triage`, `affected_files`, lock files — is
      consumed by the dashboard).
- [ ] ~8 `/triage` references in `bug-start` (describe `--triage-mode` dispatch).
- [ ] `bug-start`'s entire `--triage-mode` path (section 6.5) is only ever
      invoked *by* `/triage`; dead weight standalone, but harmless.

---

## 🟡 Dependency slimming & robustness (raised 2026-06-05)

- [ ] **Make `bmo-to-md` optional (it's REQUIRED today).** It's the
      Bugzilla-content fetcher used by `bug-start`, `triage`, and
      `download-guard` (the `bmo-to-md -a -o …` attachment pull). It's currently
      a hard requirement in `/init`, `/update` (now even *installs* it if
      missing), and the README dependency table. Demote it to **optional** with a
      graceful fallback when absent — e.g. the `moz` MCP `get_bugzilla_bug`, or a
      direct fetch of the bug's REST/HTML. Decide the fallback per consumer and
      which skills must degrade (read-bug in `bug-start`, the `/triage` fetch,
      `download-guard`'s attachment pull). Then move it below the required divider
      in `/init`, stop install-if-missing in `/update` (refresh-only when
      present), and update the README/dependency table.

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

- [ ] **Local servers' fixed ports can collide.** `/triage-dashboard` (:8765),
      Revue / `/review-dashboard` (:7777), and the `/browse` viewer each bind a
      fixed default port; a stale instance or another app on that port makes the
      launch fail or attach to the wrong server. Make port handling robust and
      consistent: auto-pick a free port when the default is busy (the viewer's
      `serve.py` and the shoot scripts already do a free-port probe — reuse that
      everywhere), surface the actual chosen port to the user, and keep the
      `PORT` override. ⚠️ **Get the specific symptom Alastor hit** (which tool,
      what error) to confirm the fix.

---

## 🟢 Cross-platform polish (win/mac/linux)

Verified: the executable code (`build_index.py`, `serve.py`) is cross-platform,
and the viewer is browser-based. The launcher was bash; now `serve.py`
(per-OS detach/kill). Remaining is unix-worded *guidance*:
- [x] `init`: Windows install notes added — `rustup-init.exe`, `nvm-windows`,
      `%USERPROFILE%\.cargo\bin` on PATH.
- [ ] Skill bash snippets (`command -v`, `~/`, `curl`, `||`) assume a POSIX
      shell — fine under Claude Code's bundled git-bash on Windows; document that
      Windows users need git-bash (Claude Code's default).
- [ ] Optional: `serve.py` could auto-open the browser per-OS
      (`open`/`xdg-open`/`start`).

## 🟢 Toolkit polish (this plugin, when we get to it)

- [ ] Consider moving the download-guard cache under the toolkit namespace too
      (`~/.cache/firefox-download-guard` → e.g. `~/.fx-bug-toolkit/download-cache`)
      for consistency with `FX_BUG_INVESTIGATION_DIR`. Touch `download-guard`,
      `bug-start` (the `bmo-to-md -a -o …` call), and `init`.
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
