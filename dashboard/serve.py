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
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import store    # storage layer: data dir, atomic writes, assemble/overlay
import collect  # fetch_bugs + user_mybug_item for user-added My work bugs

DIR = Path(__file__).resolve().parent            # the package (code) dir
# Shared theme lives one level up (assets/), same relative layout in-repo and in
# the installed plugin cache — so both the dashboard and viewer serve /theme.css.
ASSETS_DIR = DIR.parent / "assets"
# Runtime state lives under FX_DASHBOARD_DIR (~/.fx-bug-toolkit/dashboard), NOT
# the package — same convention as the rest of the toolkit.
RUN = store.run_dir()
PIDFILE = RUN / "dashboard.pid"
PORTFILE = RUN / "dashboard.port"
LOGFILE = RUN / "dashboard.log"
HOST = "127.0.0.1"
DEFAULT_PORT = 9010   # fixed default; FX_DASHBOARD_PORT overrides, busy → free-port fallback

# URLs served from the shared assets/ dir rather than the dashboard's own dir.
SHARED_ASSETS = frozenset({"/theme.css"})


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


_queue_lock = threading.Lock()     # serialize concurrent POST /queue appends
_overlay_lock = threading.Lock()   # serialize concurrent My-work add/remove


def parse_bug_id(ref: str):
    """Pull a bug id out of a bare id or a BMO URL (…show_bug.cgi?id=NNN). Returns
    the digits, or None if there's no plausible id."""
    m = re.search(r"(\d{3,})", str(ref or ""))
    return m.group(1) if m else None


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

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # Data endpoints are assembled live from the per-section files + user
        # overlay (see store.assemble); everything else is a static file (the page,
        # its JS, /theme.css). Before the first generate there are no files, so the
        # data endpoints 404 and the page shows its processing state.
        route = self.path.split("?", 1)[0].rstrip("/")
        if route == "/data.json":
            return self._send_json(store.assemble()) if store.generated() else self.send_error(404)
        if route == "/status.json":
            return self._send_json(store.status_payload()) if store.generated() else self.send_error(404)
        if route == "/queue.json":
            return self._send_json(store.read_json(store.queue_path(), []))
        if route == "/results.json":
            return self._send_json(store.read_json(store.results_path(), {}))
        return super().do_GET()

    def do_POST(self):
        # Write paths (never call Claude): queue a card action (/queue, /unqueue —
        # the drain skill processes it later) or pin/unpin a My-work bug
        # (/my-bugs/add, /my-bugs/remove — into the user overlay).
        route = self.path.split("?", 1)[0].rstrip("/")
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            self.send_error(400, "invalid JSON")
            return
        if route in ("/queue", "/unqueue"):
            with _queue_lock:
                existing = store.read_json(store.queue_path(), [])
                updated = (queue_append(existing, body) if route == "/queue"
                           else queue_remove(existing, body.get("id"), body.get("action")))
                store.atomic_write_json(store.queue_path(), updated)
            return self._send_json({"ok": True})
        if route == "/my-bugs/add":
            bid = parse_bug_id(body.get("id") or body.get("ref"))
            if not bid:
                self.send_error(400, "no bug id")
                return
            section = body.get("section")
            if section not in store.MYWORK_SECTIONS:
                section = "next"   # default: add queues it, promoting to Focus is deliberate
            detail = collect.fetch_bugs([bid], os.environ.get("BUGZILLA_API_KEY") or "").get(bid)
            if detail is not None and not detail.get("is_open"):
                return self._send_json({"ok": False, "error": "bug is closed — not added"}, 400)
            item = collect.user_mybug_item(bid, detail, datetime.now(timezone.utc))
            with _overlay_lock:
                doc = store.read_overlay_doc()
                if not any(str(i.get("id")) == bid for i in doc["items"]):
                    doc["items"].append(item)
                doc["placements"][bid] = section
                store.write_overlay_doc(doc)
            return self._send_json({"ok": True, "item": item, "section": section})
        if route == "/my-bugs/place":
            bid = parse_bug_id(body.get("id"))
            section = body.get("section")
            if not bid or section not in store.MYWORK_SECTIONS:
                self.send_error(400, "need id + valid section")
                return
            with _overlay_lock:
                doc = store.read_overlay_doc()
                doc["placements"][bid] = section
                store.write_overlay_doc(doc)
            return self._send_json({"ok": True})
        if route == "/my-bugs/reset":            # clear a manual placement → back to default
            bid = parse_bug_id(body.get("id"))
            with _overlay_lock:
                doc = store.read_overlay_doc()
                doc["placements"].pop(bid, None)
                store.write_overlay_doc(doc)
            return self._send_json({"ok": True})
        if route in ("/my-bugs/remove", "/my-bugs/dismiss"):   # ✕ on a non-assigned bug: remove for good
            bid = parse_bug_id(body.get("id"))
            with _overlay_lock:
                doc = store.read_overlay_doc()
                doc["items"] = [i for i in doc["items"] if str(i.get("id")) != bid]
                doc["placements"].pop(bid, None)
                if bid and bid not in doc["dismissed"]:
                    doc["dismissed"].append(bid)   # keep it gone even if the collector re-includes it
                store.write_overlay_doc(doc)
            return self._send_json({"ok": True})
        self.send_error(404)

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
    RUN.mkdir(parents=True, exist_ok=True)
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
