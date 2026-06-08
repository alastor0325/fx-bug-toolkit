"""Integration test: build the index and serve the viewer's static files, then
fetch every asset the page needs and validate the served index.

Fully isolated — copies the viewer assets into a temp dir and serves on an
ephemeral port, so it never touches the user's real ~/.fx-bug-toolkit data or a
running /open-investigation server.

    python3 -m unittest discover -s viewer/tests
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

VIEWER = Path(__file__).resolve().parents[1]  # viewer/tests -> viewer/
ASSETS = ["viewer.html", "viewer.logic.js", "marked.min.js", "favicon.svg"]
LAUNCHER_FILES = ASSETS + ["serve.py", "build_index.py"]

sys.path.insert(0, str(VIEWER))
import serve  # noqa: E402  — the launcher under test (no import side effects)


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


class TestServeIntegration(unittest.TestCase):
    def test_build_and_serve(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inv = root / "inv"; inv.mkdir()
            web = root / "web"; web.mkdir()

            (inv / "bug-700001-investigation.md").write_text(
                "---\nbug_id: 700001\nsummary: Served headline\n---\n# Bug 700001\nbody\n")

            for a in ASSETS:
                shutil.copy(VIEWER / a, web / a)

            # build the index into the served dir
            env = dict(os.environ,
                       FX_BUG_INVESTIGATION_DIR=str(inv),
                       FX_VIEWER_INDEX_OUT=str(web / "index.json"))
            r = subprocess.run([sys.executable, str(VIEWER / "build_index.py")],
                               env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

            port = free_port()
            srv = subprocess.Popen(
                [sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1"],
                cwd=str(web), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                base = f"http://127.0.0.1:{port}"
                # wait for readiness
                for _ in range(50):
                    try:
                        get(base + "/viewer.html"); break
                    except Exception:
                        time.sleep(0.1)
                else:
                    self.fail("server did not come up")

                # every asset the page fetches must be served
                for a in ASSETS + ["index.json"]:
                    status, _ = get(f"{base}/{a}")
                    self.assertEqual(status, 200, a)

                # the served index is valid and contains the fixture bug
                _, raw = get(base + "/index.json")
                data = json.loads(raw)
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["bug_id"], 700001)
                self.assertEqual(data[0]["summary"], "Served headline")
                self.assertTrue(data[0]["bug_url"].endswith("=700001"))

                # the page references its logic + data scripts
                _, html = get(base + "/viewer.html")
                html = html.decode()
                self.assertIn("viewer.logic.js", html)
                self.assertIn("index.json", html)
            finally:
                srv.terminate()
                srv.wait(timeout=5)


class TestServeLauncher(unittest.TestCase):
    """serve.py start/stop end-to-end, isolated in a temp copy on a free port."""

    def test_serve_py_start_and_stop(self):
        # ignore_cleanup_errors: on Windows the detached server can still hold
        # web/.run/viewer.log when the tempdir is torn down (the stop hasn't fully
        # released the handle yet) — that scaffolding race must not fail the test.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            root = Path(d)
            inv = root / "inv"; inv.mkdir()
            web = root / "web"; web.mkdir()
            (inv / "bug-800001-investigation.md").write_text(
                "---\nbug_id: 800001\nsummary: Launcher headline\n---\n# Bug 800001\nbody\n")
            for f in LAUNCHER_FILES:
                shutil.copy(VIEWER / f, web / f)

            port = free_port()
            env = dict(os.environ, FX_BUG_INVESTIGATION_DIR=str(inv), FX_VIEWER_PORT=str(port))
            serve = str(web / "serve.py")

            try:
                r = subprocess.run([sys.executable, serve, "start"], env=env,
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(f":{port}", r.stdout)

                base = f"http://127.0.0.1:{port}"
                for _ in range(50):
                    try:
                        get(base + "/viewer.html"); break
                    except Exception:
                        time.sleep(0.1)
                else:
                    self.fail("serve.py did not come up")

                self.assertEqual(get(base + "/viewer.html")[0], 200)
                _, raw = get(base + "/index.json")
                self.assertEqual(json.loads(raw)[0]["bug_id"], 800001)

                st = subprocess.run([sys.executable, serve, "status"], env=env,
                                    capture_output=True, text=True, timeout=10)
                self.assertIn("running", st.stdout)

                # restart keeps it serving
                rr = subprocess.run([sys.executable, serve, "restart"], env=env,
                                    capture_output=True, text=True, timeout=30)
                self.assertEqual(rr.returncode, 0, rr.stderr)
                for _ in range(50):
                    try:
                        if get(base + "/viewer.html")[0] == 200:
                            break
                    except Exception:
                        time.sleep(0.1)
                self.assertEqual(get(base + "/viewer.html")[0], 200)
            finally:
                subprocess.run([sys.executable, serve, "stop"], env=env,
                               capture_output=True, text=True, timeout=10)


class TestPortHelpers(unittest.TestCase):
    """Pure port-resolution helpers (no I/O)."""

    def test_url_for(self):
        self.assertEqual(serve.url_for(8777), "http://127.0.0.1:8777/viewer.html")

    def test_is_index_request(self):
        # Matches index.json regardless of the cache-busting query string.
        self.assertTrue(serve.is_index_request("/index.json"))
        self.assertTrue(serve.is_index_request("/index.json?ts=1700000000000"))
        self.assertFalse(serve.is_index_request("/viewer.html"))
        self.assertFalse(serve.is_index_request("/"))

    def test_resolve_reuses_live_instance(self):
        # A live instance with a recorded port → reuse it, ignore env.
        self.assertEqual(serve.resolve_port(9999, True, 8800), (8800, True))

    def test_resolve_env_override_when_not_running(self):
        self.assertEqual(serve.resolve_port(9999, False, None), (9999, False))

    def test_default_port_is_9000(self):
        self.assertEqual(serve.DEFAULT_PORT, 9000)

    def test_resolve_uses_default_when_nothing_set(self):
        # No env, no live instance → the fixed default port (9000).
        self.assertEqual(serve.resolve_port(None, False, None), (9000, False))

    def test_resolve_no_persisted_port_uses_default(self):
        # Alive flag but no recorded port (shouldn't reuse a guessed port) → default.
        self.assertEqual(serve.resolve_port(None, True, None), (9000, False))

    def test_resolve_default_param_is_honored(self):
        # The default is injectable (keeps the function pure/testable).
        self.assertEqual(serve.resolve_port(None, False, None, default=1234),
                         (1234, False))

    def test_is_port_free(self):
        # A port the OS just handed us is free; once an active listener holds it,
        # it isn't (even with SO_REUSEADDR, a live listening socket reads as busy).
        port = serve.pick_free_port()
        self.assertTrue(serve.is_port_free(port))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", port))
            s.listen(1)
            self.assertFalse(serve.is_port_free(port))
        finally:
            s.close()

    def test_env_port_parsing(self):
        os.environ.pop("FX_VIEWER_PORT", None)
        self.assertIsNone(serve.env_port())
        os.environ["FX_VIEWER_PORT"] = "8801"
        try:
            self.assertEqual(serve.env_port(), 8801)
            os.environ["FX_VIEWER_PORT"] = "  nope  "
            self.assertIsNone(serve.env_port())
        finally:
            os.environ.pop("FX_VIEWER_PORT", None)

    def test_pick_free_port_is_bindable(self):
        port = serve.pick_free_port()
        self.assertTrue(1024 <= port <= 65535)
        # The port the OS handed back must actually be bindable.
        s = socket.socket()
        try:
            s.bind(("127.0.0.1", port))
        finally:
            s.close()


if __name__ == "__main__":
    unittest.main()

