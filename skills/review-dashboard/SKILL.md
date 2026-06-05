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
commits a working tree has **on top of its base** (`origin/main`, else
`origin/master`, else `origin/HEAD`). So point it at the folder that holds the
work you want to review — a feature branch or a dedicated worktree with unlanded
commits — **not** a clean checkout sitting on an up-to-date `main`, which has no
series and opens an empty board.

Resolve the target, in order of preference:

1. The path passed as the skill argument, if any.
2. Otherwise, the git repo containing the current working directory.

```bash
TARGET="{argument}"   # the skill argument, or empty
if [ -n "$TARGET" ]; then
  REPO=$(cd "$TARGET" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)
else
  REPO=$(git rev-parse --show-toplevel 2>/dev/null)
fi
echo "REPO=${REPO:-<none>}"
```

If `REPO` is empty (no argument and the current directory is not inside a git
repo), **ask the user** for the path to the repo or worktree they want to
review, then re-resolve. Do not guess a path.

Then pre-flight the series, so you don't open an empty board by surprise — this
mirrors how Revue picks the base:

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

Launch Revue pointed at the resolved repo for this run (`--repo` overrides
Revue's configured default without persisting it):

```bash
revue --repo "$REPO"
```

Revue starts its daemon (default `http://localhost:7777`) and opens the browser.
Tell the user the URL and that the review board is now open for `$REPO`.

Useful follow-ups (relay if the user asks):
- `revue --restart` — restart the running instance
- `revue --stop` — stop the daemon
- `revue --port <port>` — use a non-default port
- `revue --no-open` — start the daemon without opening a browser
