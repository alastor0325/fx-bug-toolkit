---
name: open-review
description: >
  Open Revue — a local web dashboard for reviewing a git repo's patches/worktrees
  by hand and generating a review prompt to hand back to Claude. The human-review
  companion to /review (which is the AI reviewer). Triggers on "/open-review",
  "open the review dashboard", "open revue", "review board", "human review UI".
argument-hint: "[worktree-path | worktree-name] (defaults to the worktree you are working in, else your remembered Revue repo)"
allowed-tools: [Bash, AskUserQuestion]
---

# /open-review — open the Revue review dashboard

[Revue](https://github.com/alastor0325/revue) is a local web UI where **you**
review a git repo's patch series worktree by worktree — browse diffs, leave
inline comments, approve/deny per patch, and generate a structured review prompt
to paste back to Claude. It is the human-review counterpart to `/review` (the AI
reviewer). It runs as a local daemon and opens your browser.

This skill resolves **which worktree** Revue opens and launches it. It does not ship
Revue — Revue is installed lazily on first use (consent-gated).

## Step 1 — Resolve the worktree to open

Revue opens a git repo, lists **all its worktrees + patch series**, and shows
one worktree at a time. Give it the **path of the worktree to show** as `--repo`:
Revue mounts that repo's main checkout once and selects the worktree at that
path. **Do not** prompt for a worktree, pre-flight the series, or work
out Revue's worktree names yourself. Set `REPO` (and, in case 3 only,
`WORKTREE`), in order:

1. **The argument is a path** → `REPO` is that path.
2. **The argument names the work, not a path** (for example "this", a bug
   number, or a branch) → `REPO` is the absolute path of the worktree that work
   lives in. If this session works in a git worktree (for example
   `~/firefox-<bug>/`), that is "this".
3. **The argument is a worktree name that Revue shows** (for example
   `vtt-interop`) → `REPO` is the default repo (below) and `WORKTREE` is that
   name.
4. **No argument, and the session works in a git worktree** → `REPO` is that
   worktree's path.
5. **Otherwise** → `REPO` is Revue's remembered default repo (below). Do not use
   the session's cwd as a fallback when it is not a worktree you work in: it is
   often the main checkout, not the patches to review.

For cases 1 and 2, check that the path is in a git worktree:
```bash
git -C "$REPO" rev-parse --show-toplevel >/dev/null 2>&1 && echo "REPO=$REPO" || echo "not a git worktree: $REPO"
```
If it is not, tell the user and ask for a valid path.

**Default repo** (cases 3 and 5): Revue's remembered repo, `~/.revue/config.json`,
set with `revue init <path>`. Don't prompt when it is set:
```bash
PY="$(command -v python3 || command -v python)"   # python3 on macOS/Linux, python on Windows git-bash
REPO=$("$PY" -c 'import json,os;p=os.path.expanduser("~/.revue/config.json");print(json.load(open(p)).get("defaultRepo","") if os.path.exists(p) else "")' 2>/dev/null)
echo "default: ${REPO:-<none>}"
```
- **A default is set** → use it as `REPO` and go to Step 2.
- **No default is set** → ask the user once for the repo path, set `REPO` to it,
  and remember it (safe — there's nothing to clobber):
  ```bash
  revue init "$REPO"
  ```

## Step 2 — Ensure Revue ≥ 0.3.2 is installed (consent-gated)

Revue **0.3.2 or newer** is required: Step 1 relies on it selecting the
worktree at the `--repo` path, and Step 3 on one daemon serving every repo.

Check the installed version against that floor:

```bash
REQUIRED_REVUE="0.3.2"
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
  > latest (≥ 0.3.2). Requires Node.js ≥ 18.

  If the user declines, stop here and tell them `/open-review` needs Revue ≥ 0.3.2;
  they can run the command above later.

## Step 3 — Open the worktree in the running Revue

Revue keeps one daemon on one port for every repo. `revue --repo "$REPO"` adds
the repo to the Revue that is already running, or starts one. A `$WORKTREE`
name (case 3) selects that worktree.
**Do not probe, pick or remember ports.** Pass `--port` only when the user set
`$PORT`:

```bash
revue --repo "$REPO" ${WORKTREE:+"$WORKTREE"} ${PORT:+--port "$PORT"}
```

Revue prints `revue running at <URL>` and opens the browser on that worktree.
Tell the user that URL and the worktree it shows, and that the dashboard at `/`
and the dropdown next to the **Revue** wordmark switch between repos.

Useful follow-ups (relay if the user asks):
- `revue init --port <port>` — save a default port. Use it once on a remote box
  whose port is forwarded over SSH.
- `revue --restart` — restart the daemon. All open repos come back.
- `revue --stop` — stop the daemon and all its repos.
- `revue --no-open` — do not open a browser.
