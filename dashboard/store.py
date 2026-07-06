#!/usr/bin/env python3
"""Dashboard storage layer — WHERE the data lives and HOW it's read/written safely.

All dashboard runtime state lives under `FX_DASHBOARD_DIR` (default
`~/.fx-bug-toolkit/dashboard/`), NOT in the package folder — the same convention
as the rest of the toolkit (`~/.fx-bug-toolkit/…`). Three design rules keep it
race-safe without cross-process file locks:

  1. Atomic writes — write a temp file then `os.replace()` (atomic on POSIX and
     Windows), so a poller never reads a half-written file.
  2. One writer per file — the collector owns the per-section files; the server
     owns the user overlay + queue. No two processes write the same file.
  3. Derived vs. user data are separate — `my_bugs.user.json` (bugs YOU add) is a
     file the collector never touches, so a regenerate can't clobber it. The
     server merges it into `my_bugs` at read time (`assemble`).

Layout under the data dir:
    needinfos.json / reviews.json / my_bugs.json   {status, generated_at, items}
    my_bugs.user.json                              {items:[…]}   (user overlay)
    manifest.json                                  {user, sections, schema, …}
    queue.json / results.json                      (action queue + drain results)
    .run/  (pid, port, log)                         (server runtime state)

Shared by collect.py (writer) and serve.py (reader/merger); pure helpers are
unit-tested (dashboard/tests/test_store.py).
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

# Section keys, in display order (mirrors dashboard.logic.js SECTIONS).
SECTIONS = ("needinfos", "reviews", "my_bugs")
SCHEMA = 2  # bump when the on-disk shape changes incompatibly


def data_dir() -> Path:
    """Base dir for all dashboard runtime state. `FX_DASHBOARD_DIR` overrides the
    default `~/.fx-bug-toolkit/dashboard/` (toolkit convention — never the pkg)."""
    d = (os.environ.get("FX_DASHBOARD_DIR") or "").strip()
    return Path(d) if d else Path.home() / ".fx-bug-toolkit" / "dashboard"


def section_path(key: str) -> Path:
    return data_dir() / f"{key}.json"


def overlay_path() -> Path:
    return data_dir() / "my_bugs.user.json"


def manifest_path() -> Path:
    return data_dir() / "manifest.json"


def queue_path() -> Path:
    return data_dir() / "queue.json"


def results_path() -> Path:
    return data_dir() / "results.json"


def run_dir() -> Path:
    return data_dir() / ".run"


def atomic_write_json(path: Path, obj) -> None:
    """Write JSON to `path` atomically: serialize to a temp file in the same dir,
    then `os.replace()` it into place (atomic on POSIX + Windows). A concurrent
    reader sees either the old file or the new one, never a torn write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_json(path: Path, default=None):
    """Parse a JSON file, or return `default` if it's missing/unreadable/corrupt."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_section(key: str, items: list, status: str, generated_at) -> None:
    """Write one section file `{status, generated_at, items}` atomically."""
    atomic_write_json(section_path(key),
                      {"status": status, "generated_at": generated_at, "items": items})


def read_section(key: str) -> dict:
    return read_json(section_path(key),
                     {"status": "missing", "generated_at": None, "items": []})


def read_overlay() -> list:
    """The user-added my_bugs (bugs you pinned via the dashboard)."""
    d = read_json(overlay_path(), {"items": []}) or {}
    return list(d.get("items") or [])


def write_overlay(items: list) -> None:
    atomic_write_json(overlay_path(), {"items": items})


def read_manifest() -> dict:
    return read_json(manifest_path(), {}) or {}


def generated() -> bool:
    """True once a generate has ever run (the manifest exists). Before that the
    page shows its first-run processing state instead of an empty board."""
    return manifest_path().exists()


def merge_overlay(collected: list, overlay: list) -> list:
    """Union collected my_bugs with the user-added overlay, deduped by id: a
    collected bug wins (it has real patch status) but inherits the `added` flag so
    the UI still marks it pinned; a purely user-added bug is appended with
    `added: True`. Pure (new list)."""
    by_id = {str(i.get("id")): i for i in (collected or [])}
    out = list(collected or [])
    for u in overlay or []:
        uid = str(u.get("id"))
        if uid in by_id:
            by_id[uid]["added"] = True
        else:
            out.append({**u, "added": True})
    return out


def assemble() -> dict:
    """Merge the per-section files + the user overlay into the one combined shape
    the page consumes. `section_status` carries each section's own state so the UI
    can show e.g. "reviews regenerating" while the others stay live; the top-level
    `status` is "running" if any section is."""
    manifest = read_manifest()
    sections, section_status, newest = {}, {}, None
    for key in SECTIONS:
        s = read_section(key)
        sections[key] = list(s.get("items") or [])
        section_status[key] = s.get("status") or "missing"
        ga = s.get("generated_at")
        if ga and (newest is None or ga > newest):
            newest = ga
    overlay = read_overlay()
    if overlay:
        sections["my_bugs"] = merge_overlay(sections["my_bugs"], overlay)
    overall = "running" if any(v == "running" for v in section_status.values()) else "ready"
    return {
        "generated_at": manifest.get("generated_at") or newest,
        "user": manifest.get("user"),
        "status": overall,
        "schema": manifest.get("schema", SCHEMA),
        "section_status": section_status,
        "sections": sections,
    }


def status_payload() -> dict:
    """The small status doc the page polls (state + per-section counts)."""
    data = assemble()
    return {
        "state": data["status"],
        "generated_at": data["generated_at"],
        "section_status": data["section_status"],
        "counts": {k: len(v) for k, v in data["sections"].items()},
    }
