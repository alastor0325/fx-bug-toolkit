#!/usr/bin/env python3
"""Deterministic half of the dashboard drain: read the action queue, and merge the
results the drain SKILL produced back into results.json + mark those queue entries
done. The skill does the actual work (draft an NI reply, run /review, run
/bug-start) — draft-only by default; this script just moves data around.

    python3 drain.py list                 # print pending queue entries as JSON
    python3 drain.py apply results.json    # merge results, mark entries done

`results.json` is a map keyed by "<id>::<action>" → { "summary": "...", ... };
the page reads it to show each action's outcome on the card. Nothing here posts
to Bugzilla/Phabricator or touches a secret.

The pure helpers are unit-tested (dashboard/tests/test_drain.py).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import store   # queue/results live under FX_DASHBOARD_DIR (~/.fx-bug-toolkit/dashboard)

QUEUE = Path(os.environ.get("FX_DASHBOARD_QUEUE") or store.queue_path())
RESULTS = Path(os.environ.get("FX_DASHBOARD_RESULTS") or store.results_path())


def action_key(item_id, action) -> str:
    return f"{item_id}::{action}"


def pending(queue: list) -> list:
    """Queue entries not yet processed (status != 'done')."""
    return [e for e in (queue or []) if e.get("status") != "done"]


def merge_results(existing: dict, new: dict) -> dict:
    """Later results win; existing untouched results are kept. Pure."""
    out = dict(existing or {})
    out.update(new or {})
    return out


def mark_done(queue: list, keys) -> list:
    """Flip the status of any queue entry whose id::action is in `keys` to done."""
    keys = set(keys or [])
    out = []
    for e in queue or []:
        e = dict(e)
        if action_key(e.get("id"), e.get("action")) in keys:
            e["status"] = "done"
        out.append(e)
    return out


def drop_done(queue: list) -> list:
    """Prune processed entries so queue.json stays bounded to pending work — the
    card's "done" state comes from results.json, not from a done queue entry."""
    return [e for e in (queue or []) if e.get("status") != "done"]


def _load(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write(path: Path, data) -> None:
    store.atomic_write_json(path, data)


def cmd_list() -> int:
    print(json.dumps(pending(_load(QUEUE) or []), indent=2))
    return 0


def cmd_apply(results_path: str) -> int:
    new = _load(Path(results_path)) or {}
    if not isinstance(new, dict):
        print("error: results file must be a JSON object keyed by '<id>::<action>'",
              file=sys.stderr)
        return 1
    results = merge_results(_load(RESULTS) or {}, new)
    queue = drop_done(mark_done(_load(QUEUE) or [], new.keys()))
    _write(RESULTS, results)
    _write(QUEUE, queue)
    print(f"applied {len(new)} result(s); {len(queue)} still pending")
    return 0


def main(argv: list) -> int:
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "list":
        return cmd_list()
    if cmd == "apply":
        if len(argv) < 3:
            print("usage: drain.py apply <results.json>", file=sys.stderr)
            return 2
        return cmd_apply(argv[2])
    print(f"usage: {argv[0]} list | apply <results.json>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
