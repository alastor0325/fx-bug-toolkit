---
name: browse
description: Open the local Bug Investigations viewer — a fast, filterable web UI over all your investigation files (every folder, searchable, with one-line summaries). Rebuilds the index and serves it on localhost. Triggers on "browse investigations", "/browse", "open the investigation viewer", "view investigations", "investigation browser", "show my investigations".
allowed-tools: [Bash]
---

# Browse investigations

Build the index from the current investigation files and serve the local viewer,
then give the user the URL.

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$HOME/projects/fx-bug-toolkit}/viewer/serve.sh" start
```

Then:
- Tell the user it's at **http://127.0.0.1:8777/viewer.html** (the script prints
  the exact URL). Offer to open it — on macOS `open <url>`, on Linux
  `xdg-open <url>`.
- The server binds to `127.0.0.1` only, so investigation content stays local.
- It reads from `$FX_BUG_INVESTIGATION_DIR` (default
  `~/.fx-bug-toolkit/bug-investigation`), recursively across all subfolders.
- To refresh after new investigations, re-run this (it rebuilds the index), or
  `serve.sh restart`. To stop: `serve.sh stop`.

If `serve.sh` reports the port is busy, set `FX_VIEWER_PORT` to another port and
retry.
