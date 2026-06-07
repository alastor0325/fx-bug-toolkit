---
name: open-triage
description: Open the local Firefox triage dashboard — a web UI over the pending triage drafts, watch list, and investigations that /triage produces. Lazily installs the dashboard (a pip app) into a managed venv on first use, then serves it on localhost. Triggers on "/open-triage", "open the triage dashboard", "show the triage board", "triage dashboard".
allowed-tools: [Bash, AskUserQuestion]
---

# /open-triage — open the triage dashboard

The triage dashboard is a separate web app
([firefox-triage-dashboard](https://github.com/alastor0325/firefox-triage-dashboard))
that renders the drafts/watch/log/investigations `/triage` writes. It is **not**
installed by `/init` (it pulls a FastAPI stack most users don't need) — instead
it's installed **lazily, the first time it's needed**, into a managed virtualenv
at `~/.fx-bug-toolkit/venv`.

## Step 1 — Ensure the pinned version is installed (consent-gated on first use)

This plugin **pins a specific dashboard release** (`REQUIRED` below) and keeps the
managed venv on it, so `/open-triage` always runs the version this plugin was
built against — never a stale copy left over from a first install. Check what's
installed against the pin:

```bash
VENV="$HOME/.fx-bug-toolkit/venv"
BIN="$VENV/bin"; [ -d "$BIN" ] || BIN="$VENV/Scripts"   # unix vs Windows venv layout
REQUIRED="0.3.0"                                        # dashboard release this plugin targets
have=""
[ -x "$BIN/pip" ] && have="$("$BIN/pip" show triage-dashboard 2>/dev/null | sed -n 's/^Version: //p')"
if [ "$have" = "$REQUIRED" ]; then
  echo "OK ($have)"
elif [ -n "$have" ]; then
  echo "STALE ($have → $REQUIRED)"
else
  echo "NOT_INSTALLED"
fi
```

- **`OK`** — already on the pinned version; go to Step 2.
- **`STALE`** — the venv exists but is on an older dashboard. Upgrade it in place
  (fast — the heavy deps are already present), no prompt needed:
  ```bash
  VENV="$HOME/.fx-bug-toolkit/venv"; BIN="$VENV/bin"; [ -d "$BIN" ] || BIN="$VENV/Scripts"
  REQUIRED="0.3.0"
  "$BIN/pip" install --quiet --upgrade "triage-dashboard==$REQUIRED"
  echo "✅ upgraded triage dashboard to v$REQUIRED"
  ```
  Then **stop any already-running dashboard** so the new code is served — it is
  restarted in Step 2. (Match only the server process by command line; never kill
  by port — a browser tab connected to the dashboard holds a socket on that port.)
  ```bash
  pkill -9 -f "triage_dashboard.app" 2>/dev/null || pkill -9 -f "triage-dashboard" 2>/dev/null || true
  ```
- **`NOT_INSTALLED`** — one-time setup: a new venv + the dashboard and its deps
  (FastAPI/uvicorn, ~tens of MB). **Ask first** with `AskUserQuestion` (Yes/No) —
  never install without confirmation. On **Yes**:
  ```bash
  VENV="$HOME/.fx-bug-toolkit/venv"
  PY="$(command -v python3 || command -v python)"
  [ -n "$PY" ] || { echo "Python 3 is required but not on PATH (see /init)."; exit 1; }
  REQUIRED="0.3.0"
  "$PY" -m venv "$VENV"
  BIN="$VENV/bin"; [ -d "$BIN" ] || BIN="$VENV/Scripts"
  "$BIN/pip" install --quiet --upgrade pip
  "$BIN/pip" install --quiet "triage-dashboard==$REQUIRED"
  echo "✅ triage dashboard v$REQUIRED installed in $VENV"
  ```
  On **No**: stop — explain the dashboard is optional and `/triage` still works
  without it (it just writes the drafts; you won't have the web UI to review them).

## Step 2 — Start it (if not already running) and give the URL

The dashboard serves on `127.0.0.1` on an **auto-picked free port** (set `PORT` to
force one). The chosen port is remembered in `~/.fx-bug-toolkit/open-triage.port`
so a re-run reuses the running instance instead of starting a second one. Start it
detached so this skill returns; reuse it if it's already up.

```bash
VENV="$HOME/.fx-bug-toolkit/venv"
BIN="$VENV/bin"; [ -d "$BIN" ] || BIN="$VENV/Scripts"
PY="$BIN/python"; [ -x "$PY" ] || PY="$(command -v python3 || command -v python)"
LOG="$HOME/.fx-bug-toolkit/dashboard.log"
PORTFILE="$HOME/.fx-bug-toolkit/open-triage.port"
mkdir -p "$HOME/.fx-bug-toolkit"

# Reuse a still-running instance on its remembered port; otherwise pick a FRESH
# free port (never reuse a dead port — another app may now hold it). $PORT forces
# a specific port and skips reuse-detection.
REMEMBERED="$(cat "$PORTFILE" 2>/dev/null)"
if [ -z "${PORT:-}" ] && [ -n "$REMEMBERED" ] && curl -fsS -o /dev/null "http://127.0.0.1:$REMEMBERED/" 2>/dev/null; then
  echo "already running — http://127.0.0.1:$REMEMBERED/"
else
  PORT="${PORT:-$("$PY" -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1]);s.close()')}"
  URL="http://127.0.0.1:$PORT/"
  # Detach via a new session/process group so the server survives this
  # (non-interactive) shell exiting — a bare `nohup … &` is unreliable here,
  # especially on Windows. Same cross-platform approach as the viewer's serve.py.
  "$PY" - "$BIN/triage-dashboard" "$LOG" "$PORT" <<'PYEOF'
import os, subprocess, sys
exe, log, port = sys.argv[1], sys.argv[2], sys.argv[3]
kw = {"stdout": open(log, "ab"), "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
if os.name == "nt":
    kw["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
else:
    kw["start_new_session"] = True
subprocess.Popen([exe, "--host", "127.0.0.1", "--port", port, "--no-browser"], **kw)
PYEOF
  # Poll for readiness — uvicorn cold-start can exceed any fixed sleep, so
  # verify the server actually answers before claiming it's up.
  for _ in $(seq 1 20); do
    curl -fsS -o /dev/null "$URL" 2>/dev/null && break
    sleep 0.5
  done
  if curl -fsS -o /dev/null "$URL" 2>/dev/null; then
    printf '%s' "$PORT" > "$PORTFILE"   # remember it for next time's reuse check
    echo "serving — $URL"
  else
    echo "failed to start — see $LOG"; tail -5 "$LOG"
  fi
fi
```

Then tell the user the exact URL the block printed (`http://127.0.0.1:<port>/` —
the port is auto-picked, so read it from the output, don't assume a number) and
offer to open it (macOS `open`, Linux `xdg-open`, Windows `start`). The server
binds to `127.0.0.1` only — triage data stays local.

## Data it reads (shared with the rest of the toolkit)

- **Triage drafts / watch / log** from `$TRIAGE_DIR` (default `~/firefox-triage/`)
  — written by `/triage`.
- **Investigations** from `$FX_BUG_INVESTIGATION_DIR` (default
  `~/.fx-bug-toolkit/bug-investigation/`) — written by `/bug-start`; the dashboard
  serves each at `/investigation/<id>`.

Both must point at the same dirs `/triage` and `/bug-start` write to (they share
these env vars), or the board will look empty.

## Keeping it current

The dashboard version is **pinned** in Step 1 (`REQUIRED` + the `==$REQUIRED` pin
on the PyPI install). To move to a newer dashboard release, publish it to PyPI
then bump `REQUIRED` to the new version (in all three blocks above) — the next
`/open-triage` sees the mismatch (`STALE`), upgrades the venv, and restarts
the server automatically. `/update` also re-installs the pinned version. The
dashboard installs from PyPI (`pip install triage-dashboard==…`), a normal
registry install — no longer the `git+https://…` form that Claude Code's auto-mode
classifier blocks, so the agent can install/upgrade it without a denial.
