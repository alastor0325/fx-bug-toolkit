#!/usr/bin/env python3
"""Merge parallel triage-log-tmp-<id>.json files into triage-log.json.

  merge_triage_log.py [TRIAGE_DIR]

Each tmp file holds a JSON array of entries from one per-bug subagent. They are
appended to triage-log.json (created if missing) and the tmp files removed.
TRIAGE_DIR defaults to $TRIAGE_DIR, then ~/firefox-triage.
"""

import json
import os
import sys
from pathlib import Path


def merge(entries, new):
    """entries + new, skipping exact duplicates (a re-run merge)."""
    seen = {json.dumps(e, sort_keys=True) for e in entries}
    out = list(entries)
    for e in new:
        key = json.dumps(e, sort_keys=True)
        if key not in seen:
            out.append(e)
            seen.add(key)
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    root = Path(argv[0] if argv else os.environ.get("TRIAGE_DIR") or "~/firefox-triage").expanduser()
    log = root / "triage-log.json"
    entries = json.loads(log.read_text(encoding="utf-8")) if log.exists() else []
    tmps = sorted(root.glob("triage-log-tmp-*.json"))
    for tmp in tmps:
        data = json.loads(tmp.read_text(encoding="utf-8"))
        entries = merge(entries, data if isinstance(data, list) else [data])
    log.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    for tmp in tmps:
        tmp.unlink()
    print(f"merged {len(tmps)} file(s); {len(entries)} entries in {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
