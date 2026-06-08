#!/usr/bin/env python3
"""Scan the investigation directory and emit index.json for viewer.html.

Tolerant by design: only ~12% of files currently carry YAML frontmatter, so
every field except bug_id (from the filename) is optional. Files with no
frontmatter still show up — searchable by id, title, and body.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Must match the toolkit-wide default (bug-start, init): ~/.fx-bug-toolkit/bug-investigation
INVDIR = Path(os.environ.get("FX_BUG_INVESTIGATION_DIR") or (Path.home() / ".fx-bug-toolkit" / "bug-investigation"))
OUT = Path(os.environ.get("FX_VIEWER_INDEX_OUT") or (Path(__file__).resolve().parent / "index.json"))

try:
    import yaml  # pyyaml
except ImportError:
    yaml = None

_FNAME = re.compile(r"bug-(.+)-investigation\.md$")   # id may be numeric or a slug
_H1 = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
# bug-start REQUIRES a `## Security Rating` section for any sec-* / security-group
# bug (and omits it otherwise) — the canonical "this is a security bug" signal.
_SEC_HEADING = re.compile(r"(?im)^\s{0,3}#{1,6}\s+Security Rating\b")


def has_frontmatter_block(text: str) -> bool:
    """True if `text` opens a `---\\n … \\n---` frontmatter block — regardless of
    whether its YAML actually parses. Lets the indexer tell "no frontmatter"
    apart from "a block that's invalid YAML" so it can warn instead of silently
    dropping the metadata."""
    return text.startswith("---\n") and text.find("\n---", 4) != -1


def split_frontmatter(text: str):
    """Return (frontmatter_dict_or_None, body_markdown).

    `None` = no frontmatter block at all; `{}` = a block that was empty or failed
    to parse (invalid YAML). Callers distinguish the two via
    has_frontmatter_block()."""
    if not has_frontmatter_block(text):
        return None, text
    end = text.find("\n---", 4)
    fm_raw = text[4:end]
    body = text[end + 4:].lstrip("\n")
    if yaml is None:
        return {}, body
    try:
        data = yaml.safe_load(fm_raw)
        return (data if isinstance(data, dict) else {}), body
    except yaml.YAMLError:
        return {}, body


def first_title(body: str, bug_id: str) -> str:
    m = _H1.search(body)
    if m:
        # Drop a leading "Bug NNNN:" / "Bug NNNN -" prefix for a cleaner title.
        t = m.group(1).strip()
        return t
    return f"Bug {bug_id}"


def as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [x for x in v if x not in (None, "")]
    return [v]


_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")   # [text](url) -> text
_EMPH = re.compile(r"[*`]+")                     # **bold** `code` — NOT '_' (it
                                                 # is part of identifiers like
                                                 # blocking_policy)


def clean_md(s: str) -> str:
    return _EMPH.sub("", _LINK.sub(r"\1", s)).strip()


_BUGPREFIX = re.compile(r"^\s*Bug\s+\d+\b", re.IGNORECASE)
_LEADSEP = re.compile(r"^[\s—–:\-]+")


def card_label(h1: str) -> str:
    """Fallback preview text for legacy files with no `summary` field: take the
    H1 and strip the redundant 'Bug NNNN' / 'Investigation' / '(triage mode)'
    noise. This only *reads* the file's heading — it does not summarize or reason
    about content. Returns '' if nothing descriptive remains."""
    t = _BUGPREFIX.sub("", h1)
    t = _LEADSEP.sub("", t)
    t = re.sub(r"^Investigation\b", "", t, flags=re.IGNORECASE)
    t = re.sub(r"\(triage mode\)|\(triage\)", "", t, flags=re.IGNORECASE)
    t = re.sub(r"^Triage\b", "", t, flags=re.IGNORECASE)
    t = _LEADSEP.sub("", t)
    return t.strip(" —–-:()").strip()


def preview(fm: dict, h1: str, root_cause: str | None, bug_id: str) -> str:
    """The single descriptive line shown on the card / as the detail heading.
    Display-only priority: authored `summary` -> cleaned heading -> authored
    `root_cause` -> bug number. Capped so it stays preview-length."""
    s = None
    if fm.get("summary"):
        s = clean_md(str(fm["summary"]))
    if not s:
        s = card_label(h1) or None
    if not s and root_cause:
        s = clean_md(root_cause)
    if not s:
        s = f"Bug {bug_id}" if str(bug_id).isdigit() else str(bug_id).replace("-", " ")
    return (s[:217].rstrip() + "…") if len(s) > 220 else s


def date_for(fm: dict | None, path: Path) -> str:
    if fm and fm.get("investigated_at"):
        s = str(fm["investigated_at"])
        return s[:10]  # YYYY-MM-DD
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def is_security(fm: dict, body: str) -> bool:
    """True for a security investigation. The canonical signal is a
    `## Security Rating` section in the body (bug-start requires it for any
    sec-* / security-group bug); an explicit truthy `security` frontmatter field
    also counts."""
    if fm.get("security"):
        return True
    return bool(_SEC_HEADING.search(body or ""))


def main() -> int:
    if not INVDIR.is_dir():
        print(f"investigation dir not found: {INVDIR}", file=sys.stderr)
        return 1

    exclude_names = {"readme.md", "index.md"}
    items = []
    for path in sorted(INVDIR.rglob("*.md")):
        rel = path.relative_to(INVDIR)
        if any(part.startswith(".") for part in rel.parts):
            continue  # skip .git, .claude, …
        if path.name.lower() in exclude_names:
            continue
        stem = path.stem
        slug = re.sub(r"^bug-", "", stem)            # drop redundant 'bug-' prefix
        slug = re.sub(r"-investigation$", "", slug)  # …and the '-investigation' suffix
        # as_posix() so folders display with '/' on Windows too (not '\')
        folder = rel.parent.as_posix() if str(rel.parent) != "." else None
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = split_frontmatter(text)
        has_fm = fm is not None and len(fm) > 0
        if not has_fm and has_frontmatter_block(text):
            print(f"warning: {rel}: frontmatter present but did not parse "
                  f"(invalid YAML?); indexing with empty metadata", file=sys.stderr)
        fm = fm or {}
        # Real bug number (for the Bugzilla link): frontmatter bug_id, else a
        # 6-8 digit run in the filename. Slug-only files have no number.
        num = None
        if fm.get("bug_id") and str(fm["bug_id"]).isdigit():
            num = int(fm["bug_id"])
        else:
            mnum = re.search(r"\b(\d{6,8})\b", stem)
            if mnum:
                num = int(mnum.group(1))
        bug_id = num if num is not None else slug
        bug_url = f"https://bugzilla.mozilla.org/show_bug.cgi?id={num}" if num is not None else None
        root_cause = (str(fm["root_cause"]).strip() if fm.get("root_cause") else None)
        h1 = first_title(body, slug)
        summary = preview(fm, h1, root_cause, slug)
        items.append({
            "bug_id": bug_id,
            "bug_url": bug_url,
            "folder": folder,
            "summary": summary,
            "status": (fm.get("status") or "").strip() or None,
            "depth": (fm.get("depth") or "").strip() or None,
            "complexity": (fm.get("complexity") or "").strip() or None,
            "security": is_security(fm, body),
            "root_cause": root_cause,
            "affected_files": [str(x) for x in as_list(fm.get("affected_files"))],
            "related_bugs": [int(x) for x in as_list(fm.get("related_bugs")) if str(x).isdigit()],
            "investigated_at": (str(fm["investigated_at"]) if fm.get("investigated_at") else None),
            "notes": (str(fm["notes"]).strip() if fm.get("notes") else None),
            "has_frontmatter": has_fm,
            "date": date_for(fm, path),
            "body": body,
        })

    items.sort(key=lambda x: x["date"], reverse=True)
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=None), encoding="utf-8")
    with_fm = sum(1 for i in items if i["has_frontmatter"])
    folders = len({i["folder"] for i in items if i["folder"]})
    print(f"wrote {OUT} — {len(items)} files across {folders} subfolder(s) ({with_fm} with frontmatter)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
