"""Tests for the dashboard launcher: pure port/route helpers + a start/stop
integration in an isolated temp copy on a free port (never touches a running
/open-dashboard or the user's data).

    python3 -m unittest discover -s dashboard/tests
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

DASH = Path(__file__).resolve().parents[1]  # dashboard/tests -> dashboard/
# serve.py imports store + collect, so the isolated copy needs them too. Data no
# longer lives beside the code — it's under FX_DASHBOARD_DIR (a temp dir here).
LAUNCHER_FILES = ["dashboard.html", "dashboard.logic.js", "favicon.svg",
                  "serve.py", "store.py", "collect.py"]

sys.path.insert(0, str(DASH))
import serve  # noqa: E402


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.read()


class TestPortAndRouteHelpers(unittest.TestCase):
    def test_default_port_is_9010(self):
        self.assertEqual(serve.DEFAULT_PORT, 9010)

    def test_url_for(self):
        self.assertEqual(serve.url_for(9010), "http://127.0.0.1:9010/dashboard.html")

    def test_resolve_port(self):
        self.assertEqual(serve.resolve_port(9999, True, 8800), (8800, True))   # reuse live
        self.assertEqual(serve.resolve_port(9999, False, None), (9999, False))  # env override
        self.assertEqual(serve.resolve_port(None, False, None), (9010, False))  # default
        self.assertEqual(serve.resolve_port(None, True, None), (9010, False))   # alive, no port

    def test_shared_asset_target(self):
        assets = Path("/plugin/assets")
        self.assertEqual(serve.shared_asset_target("/theme.css", assets), str(assets / "theme.css"))
        self.assertEqual(serve.shared_asset_target("/theme.css?v=2", assets), str(assets / "theme.css"))
        self.assertIsNone(serve.shared_asset_target("/dashboard.html", assets))
        self.assertIsNone(serve.shared_asset_target("/data.json", assets))

    def test_env_port_parsing(self):
        os.environ.pop("FX_DASHBOARD_PORT", None)
        self.assertIsNone(serve.env_port())
        os.environ["FX_DASHBOARD_PORT"] = "8802"
        try:
            self.assertEqual(serve.env_port(), 8802)
            os.environ["FX_DASHBOARD_PORT"] = " nope "
            self.assertIsNone(serve.env_port())
        finally:
            os.environ.pop("FX_DASHBOARD_PORT", None)

    def test_queue_append_dedups_pending(self):
        e = {"id": "1", "action": "draft-reply", "status": "queued"}
        out = serve.queue_append([], e)
        self.assertEqual(len(out), 1)
        # same id+action still pending → not appended again
        self.assertEqual(len(serve.queue_append(out, dict(e))), 1)
        # a different action is appended
        self.assertEqual(len(serve.queue_append(out, {"id": "1", "action": "bug-start"})), 2)
        # same id+action but the prior one is done → the new request is allowed
        done = [{"id": "1", "action": "draft-reply", "status": "done"}]
        self.assertEqual(len(serve.queue_append(done, e)), 2)

    def test_queue_remove(self):
        q = [{"id": "1", "action": "draft-reply"}, {"id": "1", "action": "bug-start"},
             {"id": "2", "action": "draft-reply"}]
        out = serve.queue_remove(q, "1", "draft-reply")
        self.assertEqual([(e["id"], e["action"]) for e in out],
                         [("1", "bug-start"), ("2", "draft-reply")])
        # no match → unchanged
        self.assertEqual(len(serve.queue_remove(q, "9", "nope")), 3)


class TestServeLauncher(unittest.TestCase):
    def _post(self, url, obj):
        req = urllib.request.Request(url, data=json.dumps(obj).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())

    def test_start_serves_then_stops(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
            root = Path(d)
            web = root / "web"; web.mkdir()
            for f in LAUNCHER_FILES:
                shutil.copy(DASH / f, web / f)
            # serve.py routes /theme.css to ../assets — stage it as a sibling of web/
            assets = root / "assets"; assets.mkdir()
            shutil.copy(DASH.parent / "assets" / "theme.css", assets / "theme.css")
            # data lives under FX_DASHBOARD_DIR (per-section files + manifest), not
            # beside the code — seed a ready board there.
            ddir = root / "data"; ddir.mkdir()
            (ddir / "manifest.json").write_text(
                '{"user":"you@example.com","sections":["needinfos","reviews","my_bugs"],'
                '"schema":2,"generated_at":"2026-07-04T00:00:00Z"}')
            for k in ("needinfos", "reviews", "my_bugs"):
                (ddir / f"{k}.json").write_text(
                    '{"status":"ready","generated_at":"2026-07-04T00:00:00Z","items":[]}')

            port = free_port()
            env = dict(os.environ, FX_DASHBOARD_PORT=str(port), FX_DASHBOARD_DIR=str(ddir),
                       FX_BUGZILLA_BASE="http://127.0.0.1:1")   # add: fail fast, no real network
            serve_py = str(web / "serve.py")
            base = f"http://127.0.0.1:{port}"
            try:
                r = subprocess.run([sys.executable, serve_py, "start"], env=env,
                                   capture_output=True, text=True, timeout=30)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(f":{port}", r.stdout)

                for _ in range(50):
                    try:
                        get(base + "/dashboard.html"); break
                    except Exception:
                        time.sleep(0.1)
                else:
                    self.fail("dashboard serve.py did not come up")

                self.assertEqual(get(base + "/dashboard.html")[0], 200)
                # shared theme served from the sibling assets/ dir
                st, css = get(base + "/theme.css")
                self.assertEqual(st, 200)
                self.assertIn(b"--amber", css)
                # /data.json is assembled live from the per-section files
                _, raw = get(base + "/data.json")
                self.assertIn("sections", json.loads(raw))

                st = subprocess.run([sys.executable, serve_py, "status"], env=env,
                                    capture_output=True, text=True, timeout=10)
                self.assertIn("running", st.stdout)

                # POST /queue appends a card action to queue.json in the data dir
                self.assertEqual(self._post(base + "/queue",
                    {"id": "1912033", "action": "draft-reply", "type": "ni", "status": "queued"})[0], 200)
                q = json.loads(get(base + "/queue.json")[1])
                self.assertEqual((q[0]["id"], q[0]["action"]), ("1912033", "draft-reply"))
                self.assertTrue((ddir / "queue.json").exists(), "queue written to the data dir, not the pkg")

                # POST /my-bugs/add pins a bug into My work (network unreachable →
                # fetch_bugs degrades, item added with a fallback title)
                self.assertEqual(self._post(base + "/my-bugs/add", {"ref": "998877"})[0], 200)
                data = json.loads(get(base + "/data.json")[1])
                added = [b for b in data["sections"]["my_bugs"] if str(b["id"]) == "998877"]
                self.assertEqual(len(added), 1, "added bug appears in my_bugs")
                self.assertTrue(added[0]["added"], "carries the added marker")
                # POST /my-bugs/remove unpins it
                self.assertEqual(self._post(base + "/my-bugs/remove", {"id": "998877"})[0], 200)
                data = json.loads(get(base + "/data.json")[1])
                self.assertFalse(any(str(b["id"]) == "998877" for b in data["sections"]["my_bugs"]))
            finally:
                subprocess.run([sys.executable, serve_py, "stop"], env=env,
                               capture_output=True, text=True, timeout=10)


if __name__ == "__main__":
    unittest.main()
