#!/usr/bin/env python3
"""Read a bug for triage: fields, public comments, and attachment metadata.

  read_bug.py ID

Prints one JSON object between <untrusted_bug id="…"> tags that carry the
same random id. Comment text is a JSON string, so it can't pose as another
comment, another author, or the end of the data. Emails are full Bugzilla
logins (anonymous REST returns them), for needinfo targets and participant
checks. Private comments and attachments are left out. Very long comments are
cut at 8000 characters, and the oldest comments after comment 0 are dropped
when the whole thread passes 200000 characters; `omitted` says which.
"""

import json
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmo_http  # noqa: E402

BMO = "https://bugzilla.mozilla.org/rest"
BUG_FIELDS = ",".join((
    "id", "summary", "product", "component", "type", "status", "resolution", "severity",
    "priority", "keywords", "whiteboard", "cf_crash_signature", "cf_webcompat_priority",
    "url", "creator", "creator_detail", "assigned_to", "cc", "flags", "see_also",
    "regressed_by", "regressions", "blocks", "depends_on", "dupe_of", "duplicates",
    "creation_time", "last_change_time", "version", "platform", "op_sys", "groups"))
MAX_COMMENT = 8000
MAX_THREAD = 200000


def shape(bug, comments, attachments):
    """The triage view of a bug: trimmed fields, public comments, attachment list."""
    detail = bug.pop("creator_detail", None) or {}
    bug["creator_name"] = detail.get("real_name", "")
    public = [c for c in comments if not c.get("is_private")]
    out_comments, omitted, total = [], [], 0
    for c in public:
        text = c.get("text") or ""
        if len(text) > MAX_COMMENT:
            text = text[:MAX_COMMENT] + f"\n[cut at {MAX_COMMENT} characters]"
        out_comments.append({"count": c.get("count"), "creator": c.get("creator"),
                             "time": c.get("creation_time"), "tags": c.get("tags") or [],
                             "text": text})
        total += len(text)
    # Over budget: drop the oldest comments after comment 0, keep the newest.
    while total > MAX_THREAD and len(out_comments) > 2:
        dropped = out_comments.pop(1)
        omitted.append(dropped["count"])
        total -= len(dropped["text"])
    files = [{k: a.get(k) for k in ("id", "file_name", "content_type", "size", "is_obsolete",
                                    "is_patch", "summary", "creator", "creation_time")}
             for a in attachments if not a.get("is_private")]
    return {"bug": bug, "comments": out_comments, "omitted_comments": omitted, "attachments": files}


def wrap(data, token):
    return (f'<untrusted_bug id="{token}">\n{json.dumps(data, indent=1, ensure_ascii=True)}\n'
            f'</untrusted_bug id="{token}">')


def fetch(bug_id):
    bug_id = int(bug_id)
    bugs = json.loads(bmo_http.get(f"{BMO}/bug/{bug_id}?include_fields={BUG_FIELDS}"))["bugs"]
    if not bugs:
        raise LookupError(f"bug {bug_id} not found or not public")
    comments = json.loads(bmo_http.get(f"{BMO}/bug/{bug_id}/comment"))["bugs"][str(bug_id)]["comments"]
    fields = "id,file_name,content_type,size,is_obsolete,is_patch,is_private,summary,creator,creation_time"
    atts = json.loads(bmo_http.get(f"{BMO}/bug/{bug_id}/attachment?include_fields={fields}"))
    return shape(bugs[0], comments, atts.get("bugs", {}).get(str(bug_id), []))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or not argv[0].isdigit():
        print(__doc__)
        return 2
    print(wrap(fetch(argv[0]), secrets.token_hex(8)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
