#!/usr/bin/env python3
"""Cross-platform launcher for the personal dashboard (Windows/macOS/Linux).

Collects the latest data (if a collector is present), then serves dashboard/ on
127.0.0.1 in a detached background process so the caller (a skill) returns
immediately.

    python3 serve.py start | stop | restart | status

Bound to 127.0.0.1 only — your Bugzilla/Phabricator data never leaves the machine.

Port: defaults to **9010**. Set `FX_DASHBOARD_PORT` to force a different port. A
running instance is reused on its actual port; if the default is taken by another
app the launcher falls back to a free port and prints the one it used.

The shared theme is served at /theme.css from the repo-root assets/ dir (see the
`/theme.css` route), so the dashboard shares one look with the investigation
viewer — the toolkit design system.
"""
from __future__ import annotations

import http.server
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent
# Shared theme lives one level up (assets/), same relative layout in-repo and in
# the installed plugin cache — so both the dashboard and viewer serve /theme.css.
ASSETS_DIR = DIR.parent / "assets"
RUN = DIR / ".run"
PIDFILE = RUN / "dashboard.pid"
PORTFILE = RUN / "dashboard.port"
LOGFILE = RUN / "dashboard.log"
HOST = "127.0.0.1"
DEFAULT_PORT = 9010   # fixed default; FX_DASHBOARD_PORT overrides, busy → free-port fallback

# URLs served from the shared assets/ dir rather than the dashboard's own dir.
SHARED_ASSETS = frozenset({"/theme.css"})

# Card buttons POST here; the drain skill reads it. Serving never runs Claude —
# it only appends the request to this file.
QUEUE_FILE = DIR / "queue.json"


def queue_append(entries: list, entry: dict) -> list:
    """Append a card action to the queue, skipping an exact duplicate that's still
    pending (same id+action, not yet done) so double-clicks don't pile up. Pure."""
    key = (str(entry.get("id")), entry.get("action"))
    for e in entries:
        if (str(e.get("id")), e.get("action")) == key and e.get("status") != "done":
            return entries
    return entries + [entry]


def queue_remove(entries: list, item_id, action) -> list:
    """Drop the queue entry matching id+action (the card's ✕ remove). Pure."""
    return [e for e in (entries or [])
            if not (str(e.get("id")) == str(item_id) and e.get("action") == action)]


_queue_lock = threading.Lock()   # serialize concurrent POST /queue appends


def env_port() -> int | None:
    """The user's `FX_DASHBOARD_PORT` override, or None if unset/invalid."""
    v = (os.environ.get("FX_DASHBOARD_PORT") or "").strip()
    return int(v) if v.isdigit() else None


def pick_free_port() -> int:
    """Ask the OS for a free TCP port on HOST (bind to 0, read it back)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def is_port_free(port: int) -> bool:
    """True if `port` can be bound on HOST right now (nothing's actively using it)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, port))
            return True
        except OSError:
            return False


def url_for(port: int) -> str:
    return f"http://{HOST}:{port}/dashboard.html"


def resolve_port(env: int | None, alive: bool, persisted: int | None,
                 default: int = DEFAULT_PORT):
    """Which port to prefer, as `(port, reuse)`: reuse a live instance's recorded
    port; else an explicit env override; else the fixed default (caller still
    falls back to a free port if the default is busy)."""
    if alive and persisted is not None:
        return (persisted, True)
    if env is not None:
        return (env, False)
    return (default, False)


def shared_asset_target(path: str, assets_dir: Path) -> str | None:
    """Filesystem path for a shared-asset request (e.g. `/theme.css`), or None if
    `path` isn't a shared asset. Lets the dashboard serve the one canonical theme
    that lives outside its own directory, so it can't drift from the viewer."""
    clean = path.split("?", 1)[0]
    if clean in SHARED_ASSETS:
        return str(assets_dir / clean.lstrip("/"))
    return None


def _alive(pid: int) -> bool:
    if os.name == "nt":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}"],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def running_pid():
    try:
        pid = int(PIDFILE.read_text())
    except (OSError, ValueError):
        return None
    return pid if _alive(pid) else None


def read_port() -> int | None:
    try:
        return int(PORTFILE.read_text())
    except (OSError, ValueError):
        return None


class _DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dashboard/ statically, routing /theme.css to the shared assets dir.
    Everything is no-store so an open tab always re-fetches the current code/data
    (localhost dev tool; consistent with the investigation viewer)."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIR), **kwargs)

    def translate_path(self, path):
        target = shared_asset_target(path, ASSETS_DIR)
        return target if target is not None else super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        super().end_headers()

    def do_POST(self):
        # The only write paths: append (/queue) or remove (/unqueue) a card
        # action. No Claude call — the drain skill processes the queue separately.
        route = self.path.split("?", 1)[0].rstrip("/")
        if route not in ("/queue", "/unqueue"):
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self.send_error(400, "invalid JSON")
            return
        with _queue_lock:
            try:
                existing = json.loads(QUEUE_FILE.read_text())
            except (OSError, ValueError):
                existing = []
            updated = (queue_append(existing, body) if route == "/queue"
                       else queue_remove(existing, body.get("id"), body.get("action")))
            QUEUE_FILE.write_text(json.dumps(updated, indent=2))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, *args):
        pass  # quiet — the detached child's stdout/stderr go to the logfile


def _serve() -> None:  # blocking; runs in the detached child
    os.chdir(DIR)
    port = env_port() or pick_free_port()
    http.server.ThreadingHTTPServer((HOST, port), _DashboardHandler).serve_forever()


def start() -> int:
    # Serve-only: generation is a separate, explicit step (the dashboard-generate
    # skill). Opening the board never triggers the heavy pass — it just serves the
    # last generated data.json (or the page's processing state if none exists yet).
    RUN.mkdir(exist_ok=True)
    pid = running_pid()
    port, reuse = resolve_port(env_port(), pid is not None, read_port())
    if reuse:
        print(f"already serving (pid {pid}) — {url_for(port)}")
        return 0
    if env_port() is None and not is_port_free(port):
        fresh = pick_free_port()
        print(f"default port {port} is in use — falling back to free port {fresh}.")
        port = fresh
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    child_env = {**os.environ, "FX_DASHBOARD_PORT": str(port)}
    with open(LOGFILE, "ab") as log:
        p = subprocess.Popen([sys.executable, str(DIR / "serve.py"), "--serve"],
                             stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                             env=child_env, **kwargs)
    PIDFILE.write_text(str(p.pid))
    PORTFILE.write_text(str(port))
    time.sleep(1)
    if running_pid():
        print(f"serving (pid {p.pid}) — {url_for(port)}")
        return 0
    print(f"failed to start — see {LOGFILE}", file=sys.stderr)
    return 1


def stop() -> int:
    pid = running_pid()
    if not pid:
        print("not running")
        PIDFILE.unlink(missing_ok=True)
        return 0
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
    except OSError:
        pass
    PIDFILE.unlink(missing_ok=True)
    PORTFILE.unlink(missing_ok=True)
    print(f"stopped (pid {pid})")
    return 0


def status() -> int:
    pid = running_pid()
    if pid:
        print(f"running (pid {pid}) — {url_for(read_port() or DEFAULT_PORT)}")
    else:
        print("not running")
    return 0


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "start"
    if cmd == "--serve":
        _serve()
        return 0
    if cmd == "start":
        return start()
    if cmd == "stop":
        return stop()
    if cmd == "restart":
        stop()
        return start()
    if cmd == "status":
        return status()
    print(f"usage: {argv[0]} start|stop|restart|status", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
