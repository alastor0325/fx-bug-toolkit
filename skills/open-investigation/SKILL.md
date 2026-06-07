---
name: open-investigation
description: Open the local Bug Investigations viewer — a fast, filterable web UI over all your investigation files (every folder, searchable, with one-line summaries). Rebuilds the index and serves it on localhost. Triggers on "browse investigations", "/open-investigation", "open the investigation viewer", "view investigations", "investigation browser", "show my investigations".
allowed-tools: [Bash]
---

# Browse investigations

Build the index from the current investigation files and serve the local viewer,
then give the user the URL. The launcher is `serve.py` (cross-platform —
Windows/macOS/Linux). Run this exactly as-is:

```bash
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "The viewer needs Python 3, which isn't on PATH (see /init)."
else
  SERVE="$("$PY" - <<'PYEOF'
import os, glob
def first_existing(paths):
    for p in paths:
        if p and os.path.isfile(p):
            return p
    return ""
cands = []
root = os.environ.get("CLAUDE_PLUGIN_ROOT")
if root:
    cands.append(os.path.join(root, "viewer", "serve.py"))
for d in os.environ.get("PATH", "").split(os.pathsep):
    d = d.rstrip("/\\")
    if os.path.basename(d) == "bin":
        cands.append(os.path.join(os.path.dirname(d), "viewer", "serve.py"))
hit = first_existing(cands)
if not hit:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    m = glob.glob(os.path.join(base, "plugins", "cache", "**", "viewer", "serve.py"), recursive=True)
    hit = max(m, key=os.path.getmtime) if m else ""
print(hit)
PYEOF
)"
  if [ -n "$SERVE" ]; then
    echo "Serving viewer from: $SERVE"
    "$PY" "$SERVE" start
  else
    echo "Could not locate the fx-bug-toolkit viewer (serve.py). Make sure the plugin is installed and Claude Code was restarted (then try /update)."
  fi
fi
```

The launcher **echoes the resolved `serve.py`** (or a clear "could not locate"
message) so a wrong/missing path is visible, never a silent no-op.

Why this shape (don't "simplify" it): `${CLAUDE_PLUGIN_ROOT}` is **not** reliably
substituted or exported into skill Bash ([claude-code#9354](https://github.com/anthropics/claude-code/issues/9354)),
so the launcher locates `serve.py` itself — via `CLAUDE_PLUGIN_ROOT` if it
happens to be set, else the plugin's own `bin/` on `PATH`, else the Claude Code
plugin cache. Python (needed to run the viewer anyway) does the lookup so it
works the same in bash, zsh, and sh. Pick `python3`/`python` once — never
`… || python`, which prints a confusing `python: command not found` when only
`python3` exists.

Then:
- **Relay the exact URL the launcher prints** (e.g. `serving (pid …) —
  http://127.0.0.1:<port>/viewer.html`). The port is **picked automatically** —
  a free one each fresh start, persisted so a re-run reuses the same instance —
  so don't assume a fixed number; read it from the launcher's output. Offer to
  open it — macOS `open <url>`, Linux `xdg-open <url>`, Windows `start <url>`.
- The server binds to `127.0.0.1` only, so investigation content stays local.
- It reads from `$FX_BUG_INVESTIGATION_DIR` (default
  `~/.fx-bug-toolkit/bug-investigation`), recursively across all subfolders.
- To refresh after new investigations, re-run this (it rebuilds the index), or
  `serve.py restart`. To stop: `serve.py stop`.

To force a specific port, set `FX_VIEWER_PORT` before launching.
