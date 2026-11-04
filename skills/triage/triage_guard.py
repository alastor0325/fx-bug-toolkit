#!/usr/bin/env python3
"""PreToolUse hook for the locked triage runner (run_locked.py).

Bug content is untrusted, so the model's tool calls are checked here before
they run, independent of what the model was persuaded to do:

- Bash: only read-only Bugzilla/searchfox/spec/crash CLIs and this plugin's
  scripts; no shell operators, substitutions, or attachment downloads.
- Write/Edit: only inside $TRIAGE_DIR; pending drafts must pass
  validate_draft.py.
- WebFetch: documentation hosts, and public http(s) sites; never local or
  private-network targets, credentials, odd ports, or long query strings.
- Anything else that reaches the hook is denied.

Reads the hook event JSON on stdin and prints a deny decision on stdout.
"""

import ipaddress
import json
import os
import re
import shlex
import socket
import sys
import urllib.parse
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import validate_draft  # noqa: E402

# bmo-to-md, bugzilla-cli and socorro-cli are not here: their TLS/DNS fail inside
# the macOS sandbox, and bugzilla-cli reads the API key file by itself. read_bug.py,
# crash_stats.py and bmo-search cover them.
READ_ONLY_CLIS = {"bmo-search", "searchfox-cli", "webspec-index"}
SCRIPTS = {"bmo_query.py", "validate_draft.py", "read_attachment.py", "read_bug.py",
           "crash_stats.py", "merge_triage_log.py"}
PYTHONS = {"python3", "python", "python3.exe", "python.exe", "py"}
ENV_VARS = {"TRIAGE_TEAM", "TRIAGE_COMPONENTS", "TRIAGE_OWNER", "TRIAGE_DIR", "FX_TRIAGE_LOCKED"}
FETCH_HOSTS = (
    "whatwg.org", "w3.org", "w3c.github.io", "wicg.github.io", "tc39.es", "datatracker.ietf.org",
    "rfc-editor.org", "wpt.fyi", "searchfox.org", "bugzilla.mozilla.org", "hg.mozilla.org",
    "crash-stats.mozilla.org", "firefox-source-docs.mozilla.org", "developer.mozilla.org",
    "github.com", "raw.githubusercontent.com", "api.github.com", "chromestatus.com",
)


def shell_problem(command):
    """Why the command line uses shell features we don't allow, or None."""
    quote = None
    for ch in command:
        if quote == "'":
            if ch == "'":
                quote = None
            continue
        if ch in "`$":
            return "command substitution or variable expansion"
        if ch == "\\":
            return "backslash escapes"
        if quote == '"':
            if ch == '"':
                quote = None
            continue
        if ch in "'\"":
            quote = ch
        elif ch in ";&|<>(){}\n\r":
            return f"shell operator {ch!r}"
    if quote:
        return "unbalanced quotes"
    return None


def check_bash(command, plugin_dir):
    """None if allowed, else the reason to deny."""
    problem = shell_problem(command)
    if problem:
        return f"{problem} is not allowed in locked triage; run one plain command"
    try:
        argv = shlex.split(command)
    except ValueError as e:
        return f"cannot parse command: {e}"
    if not argv:
        return "empty command"
    prog = os.path.basename(argv[0])
    if prog in READ_ONLY_CLIS:
        return None
    if prog in ("bmo-to-md", "bugzilla-cli"):
        return f"{prog} is not used in locked triage; use read_bug.py <id>"
    if prog == "socorro-cli":
        return "socorro-cli is not used in locked triage; use crash_stats.py \"<signature>\""
    if prog == "printenv":
        if len(argv) > 1 and all(a in ENV_VARS for a in argv[1:]):
            return None
        return f"printenv is limited to {sorted(ENV_VARS)}"
    if prog in PYTHONS:
        if len(argv) < 2:
            return "python needs one of this plugin's scripts"
        script = Path(argv[1]).expanduser().resolve()
        if script.parent == (plugin_dir / "skills" / "triage").resolve() and script.name in SCRIPTS:
            return None
        return f"python may only run {sorted(SCRIPTS)} from this plugin"
    return f"{prog} is not allowed in locked triage"


def inside(path, root):
    try:
        Path(path).resolve().relative_to(Path(root).resolve())
        return True
    except ValueError:
        return False


def draft_id(path):
    m = re.fullmatch(r"bug-(\d+)\.json", Path(path).name)
    return int(m.group(1)) if m and Path(path).parent.name == "pending" else None


def fetch_bug(bug_id):
    """The bug as read_bug.py shapes it (the hook runs outside the Bash sandbox)."""
    import read_bug
    return read_bug.fetch(bug_id)


def check_draft_text(path, text, team, fetch=fetch_bug):
    try:
        draft = json.loads(text)
    except json.JSONDecodeError as e:
        return f"draft is not valid JSON: {e}"
    bug = None
    if isinstance(draft, dict) and (draft.get("ni_targets") or draft.get("cc_add")):
        # Needinfo and CC targets are checked against the bug's participants.
        try:
            bug = fetch(draft_id(path))
        except Exception as e:  # noqa: BLE001
            return f"could not read the bug to check needinfo/CC targets ({e}); try again"
    ran = validate_draft.browsers_run(Path(path).parent.parent, draft_id(path))
    errors, _ = validate_draft.validate(draft, team, bug, draft_id(path), locked=True, browsers_ok=ran)
    if errors:
        return "draft rejected by validate_draft.py: " + "; ".join(errors)
    return None


def check_write(tool, tool_input, triage_dir, team):
    path = tool_input.get("file_path") or ""
    if not path or not inside(path, triage_dir):
        return f"writes are limited to the triage directory ({triage_dir})"
    if Path(path).name == validate_draft.RESULTS_FILE:
        return f"{validate_draft.RESULTS_FILE} is written only by run_testcases.py"
    if draft_id(path) is None:
        return None
    if tool == "Write":
        return check_draft_text(path, tool_input.get("content") or "", team)
    try:
        current = Path(path).read_text(encoding="utf-8")
    except OSError:
        return "cannot edit a draft that does not exist; write it whole"
    old, new = tool_input.get("old_string") or "", tool_input.get("new_string") or ""
    if old not in current:
        return None  # the Edit tool itself will fail
    updated = current.replace(old, new) if tool_input.get("replace_all") else current.replace(old, new, 1)
    return check_draft_text(path, updated, team)


LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa", ".intranet", ".corp")
MAX_PUBLIC_QUERY = 200


def _global_ip(text):
    try:
        return ipaddress.ip_address(text.split("%", 1)[0]).is_global
    except ValueError:
        return None


def check_fetch(url, resolve=socket.getaddrinfo):
    """None if WebFetch may fetch url, else the reason.

    Documentation hosts are always fine. Other public http(s) pages (a site a
    bug links to) are fine too: WebFetch returns text and runs no scripts. What
    is refused: local and private-network targets (the triage dashboard on
    127.0.0.1, routers, intranet), credentials in URLs, odd ports, and long
    query strings that could smuggle data out.
    """
    parts = urllib.parse.urlsplit(url or "")
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.scheme not in ("http", "https") or not host:
        return "WebFetch takes only http(s) URLs"
    if parts.username or parts.password:
        return "URLs with credentials are not fetched"
    try:
        port = parts.port
    except ValueError:
        return "invalid port"
    if port not in (None, 80, 443):
        return "only default ports (80/443) are fetched"
    if any(host == h or host.endswith("." + h) for h in FETCH_HOSTS):
        return None
    if host == "localhost" or host.endswith(LOCAL_SUFFIXES) or "." not in host.strip("[]"):
        return f"{host} is a local name; only public sites are fetched"
    literal = _global_ip(host.strip("[]"))
    if literal is False:
        return f"{host} is not a public address"
    if len(parts.query) > MAX_PUBLIC_QUERY:
        return "query string too long; never put bug or machine data into a URL"
    if literal is None:
        try:
            addrs = {info[4][0] for info in resolve(host, port or 443, proto=socket.IPPROTO_TCP)}
        except OSError as e:
            return f"cannot resolve {host}: {e}"
        if not addrs or not all(_global_ip(a) for a in addrs):
            return f"{host} resolves to a non-public address"
    return None


def decide(event, plugin_dir, triage_dir, team):
    """None to allow, else the deny reason."""
    tool = event.get("tool_name") or ""
    tool_input = event.get("tool_input") or {}
    if tool == "Bash":
        return check_bash(tool_input.get("command") or "", plugin_dir)
    if tool in ("Write", "Edit"):
        return check_write(tool, tool_input, triage_dir, team)
    if tool == "WebFetch":
        return check_fetch(tool_input.get("url"))
    if tool in ("Read", "Glob", "Grep", "Skill", "Agent", "Task", "TodoWrite"):
        return None
    return f"{tool} is not allowed in locked triage"


def main():
    event = json.load(sys.stdin)
    plugin_dir = Path(os.environ.get("FX_TRIAGE_PLUGIN_DIR") or HERE.parent.parent)
    triage_dir = os.path.expanduser(os.environ.get("TRIAGE_DIR") or "~/firefox-triage")
    team = os.environ.get("TRIAGE_TEAM") or "av"
    reason = decide(event, plugin_dir, triage_dir, team)
    if reason:
        json.dump({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                          "permissionDecision": "deny",
                                          "permissionDecisionReason": reason}}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
