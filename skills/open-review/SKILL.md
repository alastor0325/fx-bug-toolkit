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

## Step 2 — Ensure Revue ≥ 0.1.1 is installed (consent-gated)

Revue **0.1.1 or newer** is required: earlier builds mislabelled sibling-worktree
URL hashes (e.g. `#firefox-2045395` instead of `#2045395`). Check the installed
version against that floor:

```bash
REQUIRED_REVUE="0.1.1"
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
  > latest (≥ 0.1.1). Requires Node.js ≥ 18.

  If the user declines, stop here and tell them `/open-review` needs Revue ≥ 0.1.1;
  they can run the command above later.

## Step 3 — Launch the board (port 7779, fall back if taken)

Revue serves on a **stable default port, 7779**, so you can bookmark
`http://localhost:7779/` and return to the board. Reuse a Revue that's already
answering (on 7779 or the last-used port); if **7779 is free**, take it; if it's
**taken by something else**, fall back to a free port. `$PORT` forces a specific
port. `--repo` points Revue at the resolved repo without persisting it (worktrees
are switched in Revue's UI):

```bash
PY="$(command -v python3 || command -v python)"   # python3 on macOS/Linux, python on Windows git-bash
PORTFILE="$HOME/.fx-bug-toolkit/open-review.port"
mkdir -p "$HOME/.fx-bug-toolkit"
DEFAULT_PORT="${PORT:-7779}"
REMEMBERED="$(cat "$PORTFILE" 2>/dev/null)"

# Reuse a Revue that's already up — prefer the default port, then the last-used one.
REUSED=""
for p in "$DEFAULT_PORT" "$REMEMBERED"; do
  [ -n "$p" ] && curl -fsS -o /dev/null "http://localhost:$p/" 2>/dev/null && { REUSED="$p"; break; }
done

if [ -n "$REUSED" ]; then
  echo "Revue already open — http://localhost:$REUSED/ (switch worktrees in the UI)"
else
  # Take 7779 (or $PORT) if it's free; otherwise the first free port.
  PORT="$("$PY" - "$DEFAULT_PORT" <<'PYEOF'
import socket, sys
want = int(sys.argv[1])
try:
    s = socket.socket(); s.bind(("127.0.0.1", want)); s.close(); print(want)
except OSError:
    s = socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()
PYEOF
)"
  revue --repo "$REPO" --port "$PORT"
  printf '%s' "$PORT" > "$PORTFILE"
  echo "Revue open — http://localhost:$PORT/ (switch worktrees in the UI)"
fi
```

Revue starts its daemon and opens the browser. Tell the user the exact URL the
block printed (read the port from the output — it's `7779` unless that was taken)
and that they can switch worktrees + patch series from within Revue.

Useful follow-ups (relay if the user asks):
- `revue --restart` — restart the running instance
- `revue --stop` — stop the daemon
- `revue --port <port>` — force a specific port
- `revue --no-open` — start the daemon without opening a browser
