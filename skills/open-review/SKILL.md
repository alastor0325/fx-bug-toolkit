---
name: open-review
description: >
  Open Revue — a local web dashboard for reviewing a git repo's patches/worktrees
  by hand and generating a review prompt to hand back to Claude. The human-review
  companion to /review (which is the AI reviewer). Triggers on "/open-review",
  "open the review dashboard", "open revue", "review board", "human review UI".
argument-hint: "[repo-path] (defaults to your remembered Revue repo)"
allowed-tools: [Bash, AskUserQuestion]
---

# /open-review — open the Revue review dashboard

[Revue](https://github.com/alastor0325/revue) is a local web UI where **you**
review a git repo's patch series worktree by worktree — browse diffs, leave
inline comments, approve/deny per patch, and generate a structured review prompt
to paste back to Claude. It is the human-review counterpart to `/review` (the AI
reviewer). It runs as a local daemon and opens your browser.

This skill resolves **which repo** Revue opens and launches it. It does not ship
Revue — Revue is installed lazily on first use (consent-gated).

## Step 1 — Resolve the repo to open

Revue opens a git repo and lists **all its worktrees + patch series**, and **you
switch between them in Revue's own UI**. So this skill only needs *a* repo to
point at — **do not** pre-pick a worktree, prompt for one, or pre-flight the
series. Resolve `REPO`, in order:

**1. A path was passed as the argument** → use its repo root:
```bash
REPO=$(cd "{argument}" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)
echo "REPO=${REPO:-<invalid>}"
```
If it doesn't resolve to a git repo, tell the user and ask for a valid path.

**2. No argument** → use Revue's **remembered default repo** (`~/.revue/config.json`,
set with `revue init <path>`). Don't prompt, and don't auto-pick the current
working directory (the cwd is the Claude session's dir, not the repo to review):
```bash
PY="$(command -v python3 || command -v python)"   # python3 on macOS/Linux, python on Windows git-bash
REPO=$("$PY" -c 'import json,os;p=os.path.expanduser("~/.revue/config.json");print(json.load(open(p)).get("defaultRepo","") if os.path.exists(p) else "")' 2>/dev/null)
echo "default: ${REPO:-<none>}"
```
- **A default is set** → use it as `REPO` and go straight to Step 2. (To review a
  *different* repo, the user passes a path as the argument; worktrees *within* a
  repo are switched in Revue's UI, not here.)
- **No default is set** → ask the user once for the repo path, set `REPO` to its
  repo root, and remember it (safe — there's nothing to clobber):
  ```bash
  revue init "$REPO"
  ```

## Step 2 — Ensure Revue ≥ 0.3.1 is installed (consent-gated)

Revue **0.3.1 or newer** is required. It runs one daemon for every repo on one
port, which Step 3 relies on. Earlier floors fixed the diff base for esr/beta
worktrees (0.2.0) and HEAD polling stalls (0.2.1).

Check the installed version against that floor:

```bash
REQUIRED_REVUE="0.3.1"
have="$(revue --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)"
if [ -z "$have" ]; then
  echo "NOT_INSTALLED"
elif [ "$(printf '%s\n%s\n' "$REQUIRED_REVUE" "$have" | sort -V | head -1)" = "$REQUIRED_REVUE" ]; then
  echo "OK ($have)"
else
  echo "STALE ($have < $REQUIRED_REVUE)"
fi
```

- **`OK`** — go to Step 3.
- **`NOT_INSTALLED` / `STALE`** — Revue is an **optional** dependency. Ask the user
  with `AskUserQuestion` before installing/upgrading. On yes, show the command
  first, then run it (it reinstalls in place over a stale copy):

  ```bash
  npm install -g github:alastor0325/revue
  ```

  > Install from GitHub, **not** `npm install -g revue` — the bare `revue` name on
  > the public npm registry is an unrelated package. The GitHub install pulls the
  > latest (≥ 0.3.1). Requires Node.js ≥ 18.

  If the user declines, stop here and tell them `/open-review` needs Revue ≥ 0.3.1;
  they can run the command above later.

## Step 3 — Open the repo in the running Revue

Revue keeps one daemon on one port for every repo. `revue --repo "$REPO"` adds
the repo to the Revue that is already running, or starts one. **Do not probe,
pick or remember ports.** Pass `--port` only when the user set `$PORT`:

```bash
revue --repo "$REPO" ${PORT:+--port "$PORT"}
```

Revue prints `revue running at <URL>` and opens the browser. Tell the user that
URL, and that the dashboard at `/` and the dropdown next to the **Revue**
wordmark switch between repos.

Useful follow-ups (relay if the user asks):
- `revue init --port <port>` — save a default port. Use it once on a remote box
  whose port is forwarded over SSH.
- `revue --restart` — restart the daemon. All open repos come back.
- `revue --stop` — stop the daemon and all its repos.
- `revue --no-open` — do not open a browser.
