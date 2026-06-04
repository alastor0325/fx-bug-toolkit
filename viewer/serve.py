#!/usr/bin/env python3
"""Cross-platform launcher for the investigation viewer (Windows/macOS/Linux).

Builds the index, then serves viewer/ on 127.0.0.1 in a detached background
process so the caller (a skill) returns immediately.

    python3 serve.py start | stop | restart | status

Bound to 127.0.0.1 only — investigation content never leaves the machine.
Port via FX_VIEWER_PORT (default 8777).
"""
from __future__ import annotations

import functools
import http.server
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

DIR = Path(__file__).resolve().parent
RUN = DIR / ".run"
PIDFILE = RUN / "viewer.pid"
LOGFILE = RUN / "viewer.log"
HOST = "127.0.0.1"
PORT = int(os.environ.get("FX_VIEWER_PORT", "8777"))
URL = f"http://{HOST}:{PORT}/viewer.html"


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


def build_index() -> None:
    subprocess.run([sys.executable, str(DIR / "build_index.py")])


def _serve() -> None:  # blocking; runs in the detached child
    os.chdir(DIR)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(DIR))
    http.server.ThreadingHTTPServer((HOST, PORT), handler).serve_forever()


def start() -> int:
    RUN.mkdir(exist_ok=True)
    build_index()
    pid = running_pid()
    if pid:
        print(f"already serving (pid {pid}) — {URL}")
        return 0
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    with open(LOGFILE, "ab") as log:
        p = subprocess.Popen([sys.executable, str(DIR / "serve.py"), "--serve"],
                             stdout=log, stderr=log, stdin=subprocess.DEVNULL, **kwargs)
    PIDFILE.write_text(str(p.pid))
    time.sleep(1)
    if running_pid():
        print(f"serving (pid {p.pid}) — {URL}")
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
        print(f"running (pid {pid}) — {URL}" if pid else "stopped.")
        return 0
    print("usage: serve.py {start|stop|restart|status}  (env: FX_VIEWER_PORT)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
