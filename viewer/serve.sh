#!/usr/bin/env bash
# serve.sh — build the investigation index and serve the viewer locally.
#
#   serve.sh start     build index.json + serve (background) on 127.0.0.1
#   serve.sh stop      stop the server
#   serve.sh restart   stop + start (rebuilds the index)
#   serve.sh status    is it up?
#
# Bound to 127.0.0.1 only — investigation content never leaves the machine.
# Port via FX_VIEWER_PORT (default 8777).
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
HOST=127.0.0.1
PORT="${FX_VIEWER_PORT:-8777}"
RUN="$DIR/.run"
PIDFILE="$RUN/viewer.pid"
LOGFILE="$RUN/viewer.log"
URL="http://$HOST:$PORT/viewer.html"
mkdir -p "$RUN"

running_pid() {
  [ -f "$PIDFILE" ] || return 1
  local pid; pid=$(cat "$PIDFILE" 2>/dev/null || true)
  [ -n "${pid:-}" ] && kill -0 "$pid" 2>/dev/null && { echo "$pid"; return 0; }
  return 1
}

start() {
  echo "building index…"
  python3 "$DIR/build_index.py"
  if pid=$(running_pid); then echo "already serving (pid $pid) — $URL"; return 0; fi
  ( cd "$DIR" && nohup python3 -m http.server "$PORT" --bind "$HOST" >"$LOGFILE" 2>&1 & echo $! >"$PIDFILE" )
  sleep 1
  if pid=$(running_pid); then echo "serving (pid $pid) — $URL"; else
    echo "failed to start — see $LOGFILE" >&2; return 1; fi
}

stop() {
  if pid=$(running_pid); then kill "$pid" 2>/dev/null && echo "stopped."; else echo "not running."; fi
  rm -f "$PIDFILE"
}

case "${1:-start}" in
  start)   start ;;
  stop)    stop ;;
  restart) stop; sleep 1; start ;;
  status)  if pid=$(running_pid); then echo "running (pid $pid) — $URL"; else echo "stopped."; fi ;;
  *) echo "usage: $0 {start|stop|restart|status}  (env: FX_VIEWER_PORT)"; exit 2 ;;
esac
