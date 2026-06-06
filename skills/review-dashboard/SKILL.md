---
name: review-dashboard
description: >
  Open Revue — a local web dashboard for reviewing a git repo's patches/worktrees
  by hand and generating a review prompt to hand back to Claude. The human-review
  companion to /review (which is the AI reviewer). Triggers on "/review-dashboard",
  "open the review dashboard", "open revue", "review board", "human review UI".
argument-hint: "[repo-path] (defaults to the current git repo)"
allowed-tools: [Bash, AskUserQuestion]
---

# /review-dashboard — open the Revue review dashboard

[Revue](https://github.com/alastor0325/revue) is a local web UI where **you**
review a git repo's patch series worktree by worktree — browse diffs, leave
inline comments, approve/deny per patch, and generate a structured review prompt
to paste back to Claude. It is the human-review counterpart to `/review` (the AI
reviewer). It runs as a local daemon and opens your browser.

This skill resolves **which repo** Revue opens and launches it. It does not ship
Revue — Revue is installed lazily on first use (consent-gated).

## Step 1 — Pick the folder to open

You tell Revue **which folder** to review. Revue shows a **patch series**: the
commits a working tree has on top of its base (`origin/main`, else
`origin/master`, else `origin/HEAD`). So target the folder holding the work — a
feature branch or a dedicated worktree with unlanded commits.

Revue **remembers a default repo** in `~/.revue/config.json` (set with
`revue init <path>`); plain `revue` opens it. Use that as the memory — **do not
invent a separate store**. Do **not** auto-pick from the current working
directory: when this skill runs, the cwd is the Claude session's directory, not
necessarily the repo you want to review.

Resolve the target `REPO`:

**1. A path was passed as the argument** → use it:
```bash
REPO=$(cd "{argument}" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)
echo "REPO=${REPO:-<invalid>}"
```
If it doesn't resolve to a git repo, tell the user and ask for a valid path.

**2. No path was passed** → read the remembered default and decide:
```bash
PY="$(command -v python3 || command -v python)"   # python3 on macOS/Linux, python on Windows git-bash
DEFAULT=$("$PY" -c 'import json,os;p=os.path.expanduser("~/.revue/config.json");print(json.load(open(p)).get("defaultRepo","") if os.path.exists(p) else "")' 2>/dev/null)
echo "default: ${DEFAULT:-<none>}"
```
- **A default is set** → use `AskUserQuestion` to offer two choices:
  - *Open `<DEFAULT>`* (the remembered repo) — set `REPO="$DEFAULT"`.
  - *A different folder* — then prompt for the path and set `REPO` to its repo root.
- **No default is set** → ask the user for the path to the repo/worktree to
  review, set `REPO` to its repo root, and remember it for next time (safe —
  there is no default to clobber):
  ```bash
  revue init "$REPO"
  ```

**Never silently overwrite an existing default.** If a default already exists and
the user picks a different folder, just open it for this run (Step 3 uses
`--repo`, which does not persist). Only run `revue init` on the new folder if the
user explicitly asks to make it the default.

### Pre-flight the series

Once `REPO` is resolved, check it actually has something to review, so you don't
open an empty board by surprise (this mirrors how Revue picks the base):

```bash
base=$(git -C "$REPO" rev-parse --verify -q origin/main \
     || git -C "$REPO" rev-parse --verify -q origin/master \
     || git -C "$REPO" rev-parse --verify -q origin/HEAD)
if [ -n "$base" ]; then
  echo "series: $(git -C "$REPO" rev-list --count "$base"..HEAD 2>/dev/null) commit(s) ahead of base"
else
  echo "series: base unknown (no origin/main|master|HEAD)"
fi
```

If the count is `0` (or the base is unknown), tell the user this folder has
nothing to review on top of its base, and **ask which repo or worktree** they
meant — e.g. a feature worktree with unlanded commits. Only go to Step 3 once the
target has a non-empty series, or the user explicitly says to open it anyway.

## Step 2 — Ensure Revue is installed (consent-gated on first use)

Check whether the `revue` CLI is on PATH:

```bash
command -v revue >/dev/null 2>&1 && echo "INSTALLED ($(revue --help 2>/dev/null | head -1))" || echo "NOT_INSTALLED"
```

- **`INSTALLED`** — go to Step 3.
- **`NOT_INSTALLED`** — Revue is an **optional** dependency. Ask the user with
  `AskUserQuestion` whether to install it now. Install **only** on a yes, and
  show the exact command first:

  ```bash
  npm install -g github:alastor0325/revue
  ```

  > Install from GitHub, **not** `npm install -g revue` — the bare `revue` name
  > on the public npm registry is an unrelated package. Requires Node.js ≥ 18.

  If the user declines, stop here and tell them `/review-dashboard` needs Revue;
  they can install it later with the command above.

## Step 3 — Launch the dashboard on the resolved repo

Launch Revue pointed at the resolved repo (`--repo` overrides Revue's configured
default without persisting it). Don't rely on Revue's fixed default port (7777) —
**pick a free port and pass it** so it can't collide with a stale instance or
another app, and remember it so a re-run reuses the same board instead of
spawning a second daemon (`$PORT` forces a specific port):

```bash
PY="$(command -v python3 || command -v python)"   # python3 on macOS/Linux, python on Windows git-bash
PORTFILE="$HOME/.fx-bug-toolkit/review-dashboard.port"
mkdir -p "$HOME/.fx-bug-toolkit"
REMEMBERED="$(cat "$PORTFILE" 2>/dev/null)"
if [ -z "${PORT:-}" ] && [ -n "$REMEMBERED" ] && curl -fsS -o /dev/null "http://localhost:$REMEMBERED/" 2>/dev/null; then
  echo "Revue already open — http://localhost:$REMEMBERED/ (for $REPO)"
else
  PORT="${PORT:-$("$PY" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')}"
  revue --repo "$REPO" --port "$PORT"
  printf '%s' "$PORT" > "$PORTFILE"
  echo "Revue open — http://localhost:$PORT/ (for $REPO)"
fi
```

Revue starts its daemon on the chosen port and opens the browser. Tell the user
the exact URL the block printed (read the port from the output — it's auto-picked)
and that the review board is now open for `$REPO`.

Useful follow-ups (relay if the user asks):
- `revue --restart` — restart the running instance
- `revue --stop` — stop the daemon
- `revue --port <port>` — force a specific port
- `revue --no-open` — start the daemon without opening a browser
