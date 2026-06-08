#!/usr/bin/env python3
"""Cross-platform launcher for the investigation viewer (Windows/macOS/Linux).

Builds the index, then serves viewer/ on 127.0.0.1 in a detached background
process so the caller (a skill) returns immediately.

    python3 serve.py start | stop | restart | status

Bound to 127.0.0.1 only — investigation content never leaves the machine.

Port: set `FX_VIEWER_PORT` to force a specific port; otherwise a **free port is
picked automatically** and persisted (so a fixed default can't collide with a
stale instance or another app). The chosen port is recorded in `.run/viewer.port`
so `status`/`stop` and the printed URL stay correct, and a re-`start` reuses the
running instance on its actual port.
"""
from __future__ import annotations

import http.server
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent
RUN = DIR / ".run"
PIDFILE = RUN / "viewer.pid"
PORTFILE = RUN / "viewer.port"
LOGFILE = RUN / "viewer.log"
HOST = "127.0.0.1"


def env_port() -> int | None:
    """The user's `FX_VIEWER_PORT` override, or None if unset/invalid."""
    v = (os.environ.get("FX_VIEWER_PORT") or "").strip()
    return int(v) if v.isdigit() else None


def pick_free_port() -> int:
    """Ask the OS for a free TCP port on HOST (bind to 0, read it back)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def url_for(port: int) -> str:
    return f"http://{HOST}:{port}/viewer.html"


def resolve_port(env: int | None, alive: bool, persisted: int | None):
    """Pure decision of which port to serve on.

    Returns `(port, reuse)`:
    - a live instance with a recorded port → reuse it (report that port);
    - else an explicit `FX_VIEWER_PORT` → use it;
    - else `(None, False)` → the caller should pick a fresh free port.
    """
    if alive and persisted is not None:
        return (persisted, True)
    if env is not None:
        return (env, False)
    return (None, False)


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


def build_index() -> None:
    subprocess.run([sys.executable, str(DIR / "build_index.py")])


def is_index_request(path: str) -> bool:
    """True if an HTTP request path targets index.json (ignoring any query string).
    The page fetches `index.json?ts=<nonce>`, so the query must be stripped."""
    return path.split("?", 1)[0].rstrip("/") == "/index.json"


_reindex_lock = threading.Lock()


class _ViewerHandler(http.server.SimpleHTTPRequestHandler):
    """Serves viewer/ statically, but **rebuilds the index on demand**: every
    request for index.json regenerates it from the current investigation files
    first, so a plain browser reload reflects edits without re-running the
    launcher. (Combined with the page's cache-busted, no-store fetch.)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIR), **kwargs)

    def do_GET(self):
        if is_index_request(self.path):
            with _reindex_lock:   # serialize concurrent rebuilds (ThreadingHTTPServer)
                # Rebuild IN-PROCESS — not via subprocess. Spawning python per
                # request is slow (esp. on Windows) and can blow a client's read
                # timeout; importing build_index and calling main() is fast and
                # reads the current files each call.
                import build_index
                build_index.main()
        return super().do_GET()


def _serve() -> None:  # blocking; runs in the detached child
    os.chdir(DIR)
    # The parent always passes the chosen port via FX_VIEWER_PORT; fall back to a
    # free port if somehow unset so the child never crashes on a missing value.
    port = env_port() or pick_free_port()
    http.server.ThreadingHTTPServer((HOST, port), _ViewerHandler).serve_forever()


def start() -> int:
    RUN.mkdir(exist_ok=True)
    build_index()
    pid = running_pid()
    port, reuse = resolve_port(env_port(), pid is not None, read_port())
    if reuse:
        print(f"already serving (pid {pid}) — {url_for(port)}")
        return 0
    if port is None:
        port = pick_free_port()
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    # Pin the child to the port we chose (it must not re-pick a different one).
    child_env = {**os.environ, "FX_VIEWER_PORT": str(port)}
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
    if pid:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
        else:
            os.kill(pid, signal.SIGTERM)
        print("stopped.")
    else:
        print("not running.")
    PIDFILE.unlink(missing_ok=True)
    PORTFILE.unlink(missing_ok=True)
    return 0


def main(argv) -> int:
    cmd = argv[0] if argv else "start"
    if cmd == "--serve":
        _serve(); return 0
    if cmd == "start":
        return start()
    if cmd == "stop":
        return stop()
    if cmd == "restart":
        stop(); time.sleep(1); return start()
    if cmd == "status":
        pid = running_pid()
        port = read_port()
        print(f"running (pid {pid}) — {url_for(port)}" if pid and port else "stopped.")
        return 0
    print("usage: serve.py {start|stop|restart|status}  (env: FX_VIEWER_PORT)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
