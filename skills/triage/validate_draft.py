#!/usr/bin/env python3
"""Validate a pending triage draft before it is written, shown, or applied.

Bug text is untrusted: anyone can file a bug or comment. A draft built from it
must not carry injected content to Bugzilla. This checks the fields apply would
write: allowed keys and values, needinfo/CC targets, links (allowlisted hosts
only), hidden Unicode, secrets and local paths, and team rules.

Usage: validate_draft.py <pending/bug-N.json> [--team dom-core] [--bug bug.json]
  --bug: read_bug.py or `bugzilla-cli get <id>` JSON, to check NI/CC targets
         against the bug's participants.
Exit 0 = OK (warnings may print), 1 = errors.
"""

import argparse
import json
import re
import sys
import unicodedata
import urllib.parse

ALLOWED_KEYS = {
    "bug_id", "title", "comment", "ni_targets", "priority", "severity", "blocks_add",
    "regressed_by_add", "see_also_add", "cc_add", "resolution", "keywords_add", "product",
    "component", "status", "dupe_of", "assigned_to", "created_at", "bug_context",
}
SEVERITIES = {None, "S1", "S2", "S3", "S4", "N/A"}
PRIORITIES = {None, "P1", "P2", "P3", "P4", "P5"}
RESOLUTIONS = {None, "DUPLICATE", "INVALID", "WONTFIX", "INCOMPLETE", "WORKSFORME", "FIXED"}

# Hosts a posted comment may link to. Anything else (including links the
# reporter supplied) is an error: drafts cite sources, they don't relay links.
LINK_HOSTS = (
    "bugzilla.mozilla.org", "bugzil.la", "searchfox.org", "hg.mozilla.org",
    "hg-edge.mozilla.org", "github.com", "phabricator.services.mozilla.com",
    "crash-stats.mozilla.org", "treeherder.mozilla.org", "firefox-source-docs.mozilla.org",
    "developer.mozilla.org", "wpt.fyi", "wpt.live", "web-platform-tests.org",
    "whatwg.org", "w3.org", "w3c.github.io", "wicg.github.io", "tc39.es",
    "datatracker.ietf.org", "rfc-editor.org", "chromestatus.com", "issues.chromium.org",
    "bugs.webkit.org", "mozilla.github.io", "profiler.firefox.com", "share.firefox.dev",
    "mozregression.readthedocs.io", "support.mozilla.org", "loom.com",
)

# Characters that hide or reorder text in a rendered comment.
HIDDEN = re.compile("[­؜᠎​-‏‪-‮⁠-⁤⁦-⁯﻿￹-￻]")
SECRET_PATTERNS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b"), "GitHub token"),
    (re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"), "AWS key"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"), "API key"),
    (re.compile(r"(?i)\b(?:api[_-]?key|token|secret|password)\b\s*[:=]\s*\S{8,}"), "credential assignment"),
    (re.compile(r"(?i)BUGZILLA(?:_BOT)?_API_KEY|BMO_API_KEY"), "API key variable"),
)
LOCAL_PATH = re.compile(r"(?:/Users/|/home/|[A-Za-z]:\\Users\\|~/\.|\$HOME|%USERPROFILE%)")
URL = re.compile(r"https?://[^\s<>()\"'\]]+", re.I)
EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
AI_NOTE = "(AI-assisted triage, with review.)"
CANT_TEST = re.compile(r"(?i)\b(?:couldn't|could not|can't|cannot|unable to|wasn't able to)\s+(?:test|check|run|reproduce|verify|try)")
DOM_KEYWORDS = {"spec-needed", "intermittent-failure", "regression", "testcase-wanted",
                "parity-chrome", "parity-safari", "stalled", "perf"}


def link_host_ok(url):
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in LINK_HOSTS)


def text_problems(text, field):
    """Errors for hidden characters, secrets, local paths, and off-allowlist links."""
    errors = []
    if not isinstance(text, str):
        return [f"{field}: must be a string"]
    if HIDDEN.search(text):
        errors.append(f"{field}: contains hidden or bidi control characters")
    if any(unicodedata.category(c) == "Cc" and c not in "\n\t\r" for c in text):
        errors.append(f"{field}: contains control characters")
    for pattern, what in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"{field}: looks like it contains a secret ({what})")
    if LOCAL_PATH.search(text):
        errors.append(f"{field}: contains a local machine path")
    for url in URL.findall(text):
        if not link_host_ok(url):
            errors.append(f"{field}: link to a non-allowlisted host: {url}")
    return errors


def participants(bug):
    """Emails that appear on the bug: reporter, assignee, CCs, commenters, flag setters/requestees."""
    out = set()
    if not bug:
        return out
    if isinstance(bug.get("bug"), dict):  # read_bug.py's shape
        bug = dict(bug["bug"], comments=bug.get("comments") or [])
    for key in ("creator", "assigned_to", "qa_contact"):
        if isinstance(bug.get(key), str):
            out.add(bug[key].lower())
    out.update(e.lower() for e in bug.get("cc") or [] if isinstance(e, str))
    for c in bug.get("comments") or []:
        for key in ("creator", "author"):
            if isinstance(c.get(key), str):
                out.add(c[key].lower())
    for f in bug.get("flags") or []:
        for key in ("setter", "requestee"):
            if isinstance(f.get(key), str):
                out.add(f[key].lower())
    return out


def validate(draft, team="av", bug=None, expected_id=None):
    """Return (errors, warnings) for a draft dict."""
    errors, warnings = [], []
    if not isinstance(draft, dict):
        return ["draft is not a JSON object"], []
    extra = set(draft) - ALLOWED_KEYS
    if extra:
        errors.append(f"unknown fields: {sorted(extra)}")
    bug_id = draft.get("bug_id")
    if not isinstance(bug_id, int) or bug_id <= 0:
        errors.append("bug_id must be a positive integer")
    elif expected_id is not None and bug_id != expected_id:
        errors.append(f"bug_id {bug_id} does not match the file name ({expected_id})")

    if draft.get("severity") not in SEVERITIES:
        errors.append(f"severity {draft.get('severity')!r} is not one of S1-S4/N/A/null")
    if draft.get("priority") not in PRIORITIES:
        errors.append(f"priority {draft.get('priority')!r} is not one of P1-P5/null")
    resolution = draft.get("resolution")
    if resolution not in RESOLUTIONS:
        errors.append(f"resolution {resolution!r} is not allowed")
    dupe_of = draft.get("dupe_of")
    if resolution == "DUPLICATE":
        if not isinstance(dupe_of, int) or dupe_of <= 0 or dupe_of == bug_id:
            errors.append("DUPLICATE needs dupe_of: another bug's id")
    elif dupe_of is not None:
        errors.append("dupe_of is set but resolution is not DUPLICATE")
    if bool(draft.get("product")) != bool(draft.get("component")):
        errors.append("product and component must be set together")
    for key in ("product", "component", "status", "assigned_to", "title"):
        value = draft.get(key)
        if value is not None and not isinstance(value, str):
            errors.append(f"{key} must be a string or null")
        elif isinstance(value, str):
            errors += [e for e in text_problems(value, key) if "link" not in e]

    for key in ("blocks_add", "regressed_by_add", "see_also_add"):
        value = draft.get(key) or []
        if not isinstance(value, list) or not all(isinstance(v, int) and v > 0 for v in value):
            errors.append(f"{key} must be a list of bug ids")
        elif bug_id in value:
            errors.append(f"{key} contains the bug itself")
    keywords = draft.get("keywords_add") or []
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        errors.append("keywords_add must be a list of strings")
        keywords = []
    for k in keywords:
        if k.lower().startswith(("sec-", "csectype")) or k.lower() in ("security", "topcrash"):
            errors.append(f"keywords_add: {k!r} is set by the security team or bots, not triage")

    people = participants(bug)
    for key in ("ni_targets", "cc_add"):
        value = draft.get(key) or []
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            errors.append(f"{key} must be a list of emails")
            continue
        if len(value) > 3:
            errors.append(f"{key}: at most 3 people")
        for email in value:
            if not EMAIL.match(email):
                errors.append(f"{key}: {email!r} is not an email address")
            elif bug and email.lower() not in people and not email.lower().endswith(("@mozilla.com", "@mozilla.org")):
                errors.append(f"{key}: {email} is not on the bug and not a Mozilla account")

    comment = draft.get("comment") or ""
    errors += text_problems(comment, "comment")
    if len(comment) > 4000:
        errors.append("comment: longer than 4000 characters")
    context = draft.get("bug_context") or {}
    if not isinstance(context, dict):
        errors.append("bug_context must be an object")
    elif isinstance(context.get("ai_reasoning"), str):
        errors += [e for e in text_problems(context["ai_reasoning"], "ai_reasoning") if "link" not in e]

    if team == "dom-core":
        if draft.get("priority") is not None:
            errors.append("dom-core: never set priority")
        if draft.get("assigned_to") is not None or draft.get("status") is not None:
            errors.append("dom-core: triage does not assign bugs or set status")
        if resolution == "FIXED":
            errors.append("dom-core: triage does not resolve bugs as FIXED")
        for k in keywords:
            if k not in DOM_KEYWORDS:
                warnings.append(f"keywords_add: {k!r} is unusual for dom-core triage")
        if comment.strip() and not comment.rstrip().endswith(AI_NOTE):
            errors.append(f"dom-core: a non-empty comment must end with {AI_NOTE!r}")
        words = len(URL.sub("", re.sub(r"`[^`]*`", "", comment)).split())
        if words > 300:
            warnings.append(f"comment: {words} words; check that every sentence carries a fact, pointer, or ask")
        if CANT_TEST.search(comment):
            warnings.append("comment: say what you didn't test, not that you couldn't")
    return errors, warnings


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("draft")
    ap.add_argument("--team", default="av")
    ap.add_argument("--bug", help="bugzilla-cli get output (JSON) for participant checks")
    args = ap.parse_args(argv)
    m = re.search(r"bug-(\d+)\.json$", args.draft)
    with open(args.draft, encoding="utf-8") as f:
        draft = json.load(f)
    bug = None
    if args.bug:
        with open(args.bug, encoding="utf-8") as f:
            text = f.read()
        # read_bug.py output is fenced in <untrusted_bug> tags; take the JSON inside.
        start, end = text.find("{"), text.rfind("}")
        bug = json.loads(text[start:end + 1])
        if isinstance(bug, dict) and isinstance(bug.get("bugs"), list) and bug["bugs"]:
            bug = bug["bugs"][0]
    errors, warnings = validate(draft, args.team, bug, int(m.group(1)) if m else None)
    for w in warnings:
        print(f"warning: {w}")
    for e in errors:
        print(f"error: {e}")
    print("OK" if not errors else f"{len(errors)} error(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
