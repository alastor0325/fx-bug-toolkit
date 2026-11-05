#!/usr/bin/env python3
"""Run triage testcases in browsers, with no model in the loop.

  run_testcases.py [--triage-dir DIR] [--browsers firefox,chrome,safari]
                   [--bug ID ...] [--since EPOCH]

A locked triage run (run_locked.py) can't drive browsers: the model has read
untrusted bug content. Instead it saves the testcases it writes to
`testcases/bug-<id>.html`, and this script, which runs no model, loads each one
in Firefox Nightly, Chrome Canary and Safari TP over WebDriver and records what
the page reports in `window.testcaseResult`. Results go to
`testcase-results.json`, which only this script writes.

Testcases are written by a model that read untrusted text, so:
- only bugs that are public, not security-sensitive, and not crashes, hangs or
  assertions are run, checked against Bugzilla, not the draft;
- a testcase with absolute or protocol-relative URLs, navigation, meta
  refresh, string-decoding helpers, or an escaped ':' or '/' is refused unrun
  (a best-effort check; the CSP and proxy below are what block traffic);
- pages are served from 127.0.0.1 with a CSP that allows only that origin, so
  subresources, fetches and form posts can't leave the machine; Firefox and
  Chrome also get a dead proxy, so nothing else does either. Safari TP has no
  proxy setting, so a scripted top-level navigation is the one gap left there;
- every testcase gets a fresh browser session (fresh profile), headless where
  the browser supports it, with the browser's own sandbox on;
- afterwards nothing is left running: each driver runs in its own process
  group, which is killed with every browser process in it, and the Safari TP
  instance safaridriver started (which outlives its sessions) is quit.

Drivers and binaries: geckodriver and chromedriver from PATH, or
FX_TRIAGE_GECKODRIVER / FX_TRIAGE_CHROMEDRIVER; browsers from the usual install
paths, or FX_TRIAGE_FIREFOX / FX_TRIAGE_CHROME. Safari TP uses its own
safaridriver (enable it once with `safaridriver --enable` from the Safari
Technology Preview app bundle).
"""

import argparse
import datetime
import hashlib
import http.server
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bmo_http  # noqa: E402
import validate_draft  # noqa: E402

BMO = "https://bugzilla.mozilla.org/rest"
BROWSERS = ("firefox", "chrome", "safari")
MAX_TESTCASE = 100_000
MAX_RESULT = 2000
RESULT_WAIT_MS = 5000
TESTCASE_NAME = re.compile(r"bug-(\d+)\.html")
CSP = ("default-src 'self' 'unsafe-inline' 'unsafe-eval' data: blob:; "
       "form-action 'self'; base-uri 'none'")
# A port nothing listens on: Firefox and Chrome send all non-local traffic here.
DEAD_PROXY = "127.0.0.1:9"

REFUSED = (
    (re.compile(r"(?i)\b[a-z][a-z0-9+.-]*:\s*/\s*/"), "an absolute URL"),
    (re.compile(r"(?i)(?:src|href|action|data|poster|srcset|background|ping|manifest)\s*=\s*[\"']?\s*//"),
     "a protocol-relative URL"),
    (re.compile(r"(?i)url\(\s*[\"']?\s*//"), "a protocol-relative URL"),
    (re.compile(r"(?i)@import"), "@import"),
    (re.compile(r"(?i)<meta[^>]+http-equiv"), "a meta http-equiv"),
    (re.compile(r"(?i)(?<![\w.])open\s*\(|\bwindow\s*\.\s*open\s*\("), "window.open"),
    (re.compile(r"(?i)\blocation\s*(?:\.\s*(?:href|assign|replace|host|hostname|protocol|port|pathname|search)\s*)?(?:=(?!=)|\()"),
     "navigation"),
    (re.compile(r"(?i)\b(?:fromCharCode|fromCodePoint|atob|unescape|decodeURI(?:Component)?)\b"),
     "string decoding"),
    (re.compile(r"(?i)&(?:#0*(?:58|47);?|#x0*(?:3a|2f);?|colon;|sol;)|\\(?:x3a|x2f|u003a|u002f|u\{0*(?:3a|2f)\})"),
     "an escaped ':' or '/'"),
)

FIREFOX_BINARIES = {
    "darwin": "/Applications/Firefox Nightly.app/Contents/MacOS/firefox",
    "win32": r"C:\Program Files\Firefox Nightly\firefox.exe",
    "linux": "firefox-nightly",
}
CHROME_BINARIES = {
    "darwin": "/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary",
    "win32": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome SxS\Application\chrome.exe"),
    "linux": "google-chrome-unstable",
}
SAFARI_DRIVER = "/Applications/Safari Technology Preview.app/Contents/MacOS/safaridriver"
# The app safaridriver launches for automation; it isn't the driver's child.
SAFARI_AUTOMATION = re.compile(r"/Safari Technology Preview\.app/Contents/MacOS/Safari Technology Preview\b.*--automation")

POLL_SCRIPT = """
const done = arguments[arguments.length - 1];
const start = Date.now();
(function poll() {
  if (window.testcaseResult !== undefined) {
    const v = window.testcaseResult;
    let r;
    try { r = typeof v === "string" ? v : JSON.stringify(v); } catch (e) { r = String(v); }
    done({result: String(r), url: location.href});
  } else if (Date.now() - start > %d) {
    done({result: null, url: location.href});
  } else {
    setTimeout(poll, 50);
  }
})();
""" % RESULT_WAIT_MS


def testcase_problems(text):
    """Reasons a testcase must not be run, or []."""
    if len(text) > MAX_TESTCASE:
        return [f"larger than {MAX_TESTCASE} characters"]
    return sorted({why for pattern, why in REFUSED if pattern.search(text)})


def skip_reason(bug):
    """Why a bug's testcase must not run (from Bugzilla's fields), or None."""
    if not bug:
        return "bug is not public"
    if bug.get("groups"):
        return "bug is restricted"
    for k in bug.get("keywords") or []:
        k = k.lower()
        if k.startswith(("sec-", "csectype")) or k in ("security", "crash", "hang", "assertion"):
            return f"keyword {k}"
    if (bug.get("cf_crash_signature") or "").strip():
        return "bug has a crash signature"
    if re.search(r"(?i)\b(?:crash|hang|assert)", bug.get("summary") or ""):
        return "summary mentions a crash, hang or assertion"
    return None


def fetch_bug(bug_id):
    url = f"{BMO}/bug/{int(bug_id)}?include_fields=id,summary,keywords,cf_crash_signature,groups"
    try:
        bugs = json.loads(bmo_http.get(url)).get("bugs") or []
    except OSError:
        return None
    return bugs[0] if bugs else None


def select(triage_dir, bugs=None, since=None):
    """{bug id: testcase path} for testcases that have a pending draft."""
    found = {}
    folder = Path(triage_dir) / "testcases"
    if not folder.is_dir():
        return found
    for path in sorted(folder.iterdir()):
        m = TESTCASE_NAME.fullmatch(path.name)
        if not m or path.is_symlink() or not path.is_file():
            continue
        bug_id = int(m.group(1))
        if bugs and bug_id not in bugs:
            continue
        if since is not None and path.stat().st_mtime < since:
            continue
        if (Path(triage_dir) / "pending" / f"bug-{bug_id}.json").is_file():
            found[bug_id] = path
    return found


def capabilities(browser, binary=None):
    """New Session capabilities: fresh profile, no network beyond 127.0.0.1."""
    proxy = {"proxyType": "manual", "httpProxy": DEAD_PROXY, "sslProxy": DEAD_PROXY,
             "noProxy": ["127.0.0.1"]}
    if browser == "firefox":
        caps = {"browserName": "firefox", "proxy": proxy, "moz:firefoxOptions": {
            "args": ["-headless"],
            "prefs": {"network.proxy.allow_hijacking_localhost": False,
                      "network.dns.disabled": True}}}
        if binary:
            caps["moz:firefoxOptions"]["binary"] = binary
    elif browser == "chrome":
        caps = {"browserName": "chrome", "proxy": proxy, "goog:chromeOptions": {
            "args": ["--headless=new", "--no-first-run", "--disable-background-networking",
                     "--disable-component-update", "--disable-sync", "--disable-extensions",
                     "--disable-default-apps"]}}
        if binary:
            caps["goog:chromeOptions"]["binary"] = binary
    elif browser == "safari":
        caps = {"browserName": "Safari Technology Preview"}
    else:
        raise ValueError(browser)
    return {"capabilities": {"alwaysMatch": caps}}


def _binary(env_var, defaults, env, platform):
    value = env.get(env_var) or defaults.get(platform if platform in defaults else "linux")
    if not value:
        return None
    if os.path.isabs(value):
        return value if os.path.exists(value) else None
    return shutil.which(value)


def find_browser(browser, env=None, platform=sys.platform):
    """(driver argv for a port, browser binary or None), or None if unavailable."""
    env = os.environ if env is None else env
    if browser == "firefox":
        driver = env.get("FX_TRIAGE_GECKODRIVER") or shutil.which("geckodriver")
        binary = _binary("FX_TRIAGE_FIREFOX", FIREFOX_BINARIES, env, platform)
        return (lambda port: [driver, "--port", str(port)], binary) if driver and binary else None
    if browser == "chrome":
        driver = env.get("FX_TRIAGE_CHROMEDRIVER") or shutil.which("chromedriver")
        binary = _binary("FX_TRIAGE_CHROME", CHROME_BINARIES, env, platform)
        return (lambda port: [driver, f"--port={port}"], binary) if driver and binary else None
    if browser == "safari" and platform == "darwin" and os.path.exists(SAFARI_DRIVER):
        return (lambda port: [SAFARI_DRIVER, "-p", str(port)], None)
    return None


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start_process(argv):
    """Start argv in a new process group, so its browsers can be killed with it."""
    if os.name == "nt":
        return subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    return subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)


def stop_process(proc, grace=10):
    """Stop a driver and every process in its group, browsers included."""
    if os.name == "nt":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.kill()
        proc.wait()
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(proc.pid, sig)
        except (ProcessLookupError, PermissionError):
            break
        try:
            proc.wait(grace)
        except subprocess.TimeoutExpired:
            pass
        if sig == signal.SIGTERM:
            time.sleep(0.5)  # let the browsers exit before the group is killed
    proc.wait()


def automation_safari_pids(ps_output=None):
    """Pids of Safari TP instances started for automation."""
    if ps_output is None:
        if sys.platform != "darwin":
            return set()
        ps_output = subprocess.run(["ps", "-axo", "pid=,command="], capture_output=True,
                                   text=True).stdout
    pids = set()
    for line in ps_output.splitlines():
        pid, _, command = line.strip().partition(" ")
        if pid.isdigit() and SAFARI_AUTOMATION.search(command):
            pids.add(int(pid))
    return pids


def quit_pids(pids, grace=10):
    """SIGTERM pids, then SIGKILL the ones still running after `grace` seconds."""
    if not pids or os.name == "nt":
        return
    for sig in (signal.SIGTERM, signal.SIGKILL):
        alive = set()
        for pid in pids:
            try:
                os.kill(pid, sig)
                alive.add(pid)
            except (ProcessLookupError, PermissionError):
                pass
        deadline = time.time() + grace
        while alive and time.time() < deadline:
            time.sleep(0.25)
            alive = {pid for pid in alive if _running(pid)}
        pids = alive
        if not pids:
            return


def _running(pid):
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


class Driver:
    """A WebDriver server process and a tiny client for it."""

    def __init__(self, argv_for_port):
        self.port = free_port()
        self.safari_before = automation_safari_pids()
        self.proc = start_process(argv_for_port(self.port))
        self.base = f"http://127.0.0.1:{self.port}"
        deadline = time.time() + 20
        while time.time() < deadline:
            try:
                if self.call("GET", "/status", timeout=2).get("ready", True):
                    return
            except (OSError, ValueError):
                pass
            time.sleep(0.25)
        self.close()
        raise OSError("driver did not start")

    def call(self, method, path, body=None, timeout=60):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read() or b"{}").get("value") or {}
        except urllib.error.HTTPError as e:
            try:
                value = json.loads(e.read() or b"{}").get("value") or {}
            except ValueError:
                value = {}
            raise OSError(f"{value.get('error', e.code)}: {str(value.get('message', ''))[:200]}") from None

    def close(self):
        stop_process(self.proc)
        # safaridriver's Safari TP outlives its sessions and isn't in the group.
        quit_pids(automation_safari_pids() - self.safari_before)


def run_one(driver, browser, binary, url):
    """Load url in a fresh session; {status, version, result}."""
    session = driver.call("POST", "/session", capabilities(browser, binary))
    sid = session["sessionId"]
    out = {"version": str(session.get("capabilities", {}).get("browserVersion", ""))}
    try:
        driver.call("POST", f"/session/{sid}/timeouts",
                    {"pageLoad": 15000, "script": RESULT_WAIT_MS + 5000})
        driver.call("POST", f"/session/{sid}/url", {"url": url})
        value = driver.call("POST", f"/session/{sid}/execute/async",
                            {"script": POLL_SCRIPT, "args": []}, timeout=30)
        out.update(interpret(value, url))
    finally:
        try:
            driver.call("DELETE", f"/session/{sid}", timeout=20)
        except OSError:
            pass
    return out


def interpret(value, url):
    """Turn the page's report into a result entry."""
    if not isinstance(value, dict) or value.get("url") != url:
        return {"status": "navigated", "result": None}
    if value.get("result") is None:
        return {"status": "timeout", "result": None}
    return {"status": "ok", "result": str(value["result"])[:MAX_RESULT]}


class _Handler(http.server.BaseHTTPRequestHandler):
    pages = {}

    def do_GET(self):  # noqa: N802
        body = self.pages.get(self.path.split("?", 1)[0].lstrip("/"))
        self.send_response(200 if body is not None else 404)
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Type", "text/html; charset=utf-8")
        body = body if body is not None else b"not found"
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def serve(pages):
    """Serve {name: bytes} on 127.0.0.1 with the CSP; returns the server."""
    handler = type("Handler", (_Handler,), {"pages": dict(pages)})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def load_results(triage_dir):
    path = Path(triage_dir) / validate_draft.RESULTS_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def run(triage_dir, browsers, bugs=None, since=None, fetch=fetch_bug, log=print):
    """Run the selected testcases; update and return the results file's data."""
    results = load_results(triage_dir)
    pages, entries = {}, {}
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    for bug_id, path in select(triage_dir, bugs, since).items():
        text = path.read_text(encoding="utf-8", errors="replace")
        entry = {"ran_at": now, "sha256": hashlib.sha256(text.encode()).hexdigest()}
        reason = skip_reason(fetch(bug_id))
        problems = testcase_problems(text)
        if reason or problems:
            entry["skipped"] = reason or "testcase contains " + ", ".join(problems)
            log(f"bug {bug_id}: skipped ({entry['skipped']})")
        else:
            pages[path.name] = text.encode()
            entry["browsers"] = {}
        entries[bug_id] = entry
    if pages:
        server = serve(pages)
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            for browser in browsers:
                found = find_browser(browser)
                if not found:
                    log(f"{browser}: not available")
                    continue
                try:
                    driver = Driver(found[0])
                except OSError as e:
                    log(f"{browser}: {e}")
                    continue
                try:
                    for bug_id, entry in entries.items():
                        if "browsers" not in entry:
                            continue
                        try:
                            res = run_one(driver, browser, found[1], f"{base}/bug-{bug_id}.html")
                        except (OSError, KeyError, ValueError) as e:
                            res = {"status": "error", "result": None, "error": str(e)[:300]}
                        entry["browsers"][browser] = res
                        log(f"bug {bug_id}: {browser} {res['status']}")
                finally:
                    driver.close()
        finally:
            server.shutdown()
            server.server_close()
    for bug_id, entry in entries.items():
        results[str(bug_id)] = entry
    path = Path(triage_dir) / validate_draft.RESULTS_FILE
    path.write_text(json.dumps(results, indent=1) + "\n", encoding="utf-8")
    return results


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--triage-dir", default=os.environ.get("TRIAGE_DIR", "~/firefox-triage"))
    ap.add_argument("--browsers", default=",".join(BROWSERS))
    ap.add_argument("--bug", type=int, action="append", help="repeatable; default: all with a draft")
    ap.add_argument("--since", type=float, help="only testcases modified after this Unix time")
    args = ap.parse_args(argv)
    browsers = [b for b in args.browsers.split(",") if b]
    unknown = set(browsers) - set(BROWSERS)
    if unknown:
        ap.error(f"unknown browsers: {sorted(unknown)}")
    run(os.path.expanduser(args.triage_dir), browsers, args.bug, args.since)
    return 0


if __name__ == "__main__":
    sys.exit(main())
