---
name: open-dashboard
description: >
  Open your personal dashboard — a local web board of your Bugzilla needinfos,
  Phabricator review requests, and the bugs you're working on, with briefs, tags,
  and per-card actions. Serves the LAST generated data instantly; run
  /dashboard-generate to (re)build the data. Triggers on "/open-dashboard",
  "open my dashboard", "show my dashboard", "open the dashboard".
allowed-tools: [Bash]
---

# Open the personal dashboard

Serve-only: this **never** runs the heavy analysis — it just serves the latest
data `/dashboard-generate` produced, so the board opens instantly. If nothing has
been generated yet, the page shows a processing state; tell the user to run
`/dashboard-generate` first.

Locate the launcher itself (`${CLAUDE_PLUGIN_ROOT}` isn't reliably exported into
skill Bash — same approach as `/open-investigation`) and start it:

```bash
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "The dashboard needs Python 3, which isn't on PATH (see /init)."
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
    cands.append(os.path.join(root, "dashboard", "serve.py"))
for d in os.environ.get("PATH", "").split(os.pathsep):
    d = d.rstrip("/\\")
    if os.path.basename(d) == "bin":
        cands.append(os.path.join(os.path.dirname(d), "dashboard", "serve.py"))
hit = first_existing(cands)
if not hit:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    m = glob.glob(os.path.join(base, "plugins", "cache", "**", "dashboard", "serve.py"), recursive=True)
    hit = max(m, key=os.path.getmtime) if m else ""
print(hit)
PYEOF
)"
  if [ -n "$SERVE" ]; then
    echo "Serving dashboard from: $SERVE"
    "$PY" "$SERVE" start
  else
    echo "Could not locate the dashboard (serve.py). Make sure the plugin is installed and Claude Code was restarted (then try /update)."
  fi
fi
```

Then:
- **Relay the exact URL the launcher prints** (e.g. `serving (pid …) —
  http://127.0.0.1:<port>/dashboard.html`). Default port **9010**; a running
  instance is reused, and if 9010 is taken the launcher falls back to a free port
  — so read the actual URL from the output rather than assuming 9010. Offer to
  open it (macOS `open <url>`, Linux `xdg-open <url>`, Windows `start <url>`).
- Bound to `127.0.0.1` only — your data stays local. `FX_DASHBOARD_PORT` forces a
  port; `serve.py restart` / `stop` manage it.
- **If the board shows "Generating…" and never fills**, no data has been
  generated yet — run **`/dashboard-generate`**. To refresh the data, run
  `/dashboard-generate` again; the open page picks it up automatically.
