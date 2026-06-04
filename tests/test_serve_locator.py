"""Guards the shipped serve.py locator embedded in the browse / bug-start skills.

The skills can't rely on ${CLAUDE_PLUGIN_ROOT} in Bash (claude-code#9354), so each
ships an inline Python snippet that locates viewer/serve.py via, in order:
  1. $CLAUDE_PLUGIN_ROOT
  2. the plugin's own bin/ on $PATH (the signal that survives on Linux/bash)
  3. the Claude Code plugin cache (covers shells whose rc clobbers PATH)

This extracts the *actual* snippet from the SKILL.md files and runs it, so the
test breaks if the shipped resolver regresses.

    python3 -m unittest discover -s tests
"""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[1] / "skills"
BROWSE = SKILLS / "browse" / "SKILL.md"
BUGSTART = SKILLS / "bug-start" / "SKILL.md"

# pull the python heredoc body:  <<'PYEOF' ... PYEOF
HEREDOC = re.compile(r"<<'PYEOF'\n(.*?)\nPYEOF", re.DOTALL)


def extract_locator(skill_md: Path) -> str:
    # utf-8 explicitly — the SKILL.md files contain emoji/arrows, and Windows
    # would otherwise decode with cp1252 and raise UnicodeDecodeError.
    m = HEREDOC.search(skill_md.read_text(encoding="utf-8"))
    assert m, f"no PYEOF heredoc found in {skill_md}"
    return m.group(1)


def run_locator(snippet: str, env: dict) -> str:
    full = dict(os.environ)
    # start from a clean slate for the vars the locator reads
    for k in ("CLAUDE_PLUGIN_ROOT", "CLAUDE_CONFIG_DIR"):
        full.pop(k, None)
    full.update(env)
    out = subprocess.run(
        [sys.executable, "-c", snippet],
        env=full, capture_output=True, text=True, timeout=15,
    )
    assert out.returncode == 0, out.stderr
    return out.stdout.strip()


def make_plugin(tmp: Path) -> Path:
    """A realistic install layout: <cache>/<mkt>/<plugin>/<ver>/{bin,viewer}."""
    root = tmp / ".claude" / "plugins" / "cache" / "fx-bug-toolkit" / "fx-bug-toolkit" / "0.2.0"
    (root / "bin").mkdir(parents=True)
    (root / "viewer").mkdir(parents=True)
    (root / "viewer" / "serve.py").write_text("# fixture\n")
    return root


class TestServeLocator(unittest.TestCase):
    def setUp(self):
        self.snippet = extract_locator(BROWSE)

    def test_strategy1_plugin_root_env(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_plugin(Path(d))
            hit = run_locator(self.snippet, {
                "CLAUDE_PLUGIN_ROOT": str(root),
                "PATH": "/usr/bin:/bin",
            })
            self.assertEqual(hit, str(root / "viewer" / "serve.py"))

    def test_strategy2_bin_sibling_on_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_plugin(Path(d))
            hit = run_locator(self.snippet, {
                "PATH": os.pathsep.join([str(root / "bin"), "/usr/bin", "/bin"]),
            })
            self.assertEqual(hit, str(root / "viewer" / "serve.py"))

    def test_strategy3_plugin_cache_glob(self):
        # No env var, PATH clobbered — only the cache under CLAUDE_CONFIG_DIR remains.
        with tempfile.TemporaryDirectory() as d:
            root = make_plugin(Path(d))
            hit = run_locator(self.snippet, {
                "PATH": "/usr/bin:/bin",
                "CLAUDE_CONFIG_DIR": str(Path(d) / ".claude"),
            })
            self.assertEqual(hit, str(root / "viewer" / "serve.py"))

    def test_negative_nothing_found(self):
        with tempfile.TemporaryDirectory() as d:
            hit = run_locator(self.snippet, {
                "PATH": "/usr/bin:/bin",
                "CLAUDE_CONFIG_DIR": str(Path(d) / "empty"),
            })
            self.assertEqual(hit, "")

    def test_ignores_non_bin_path_entries(self):
        # a PATH dir whose sibling has viewer/serve.py but the dir isn't named "bin"
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "plugin"
            (root / "scripts").mkdir(parents=True)
            (root / "viewer").mkdir(parents=True)
            (root / "viewer" / "serve.py").write_text("# fixture\n")
            hit = run_locator(self.snippet, {
                "PATH": os.pathsep.join([str(root / "scripts"), "/usr/bin", "/bin"]),
                "CLAUDE_CONFIG_DIR": str(Path(d) / "empty"),
            })
            self.assertEqual(hit, "")  # "scripts" != "bin", and no cache → not found

    def test_browse_and_bugstart_share_one_locator(self):
        # the two skills must ship the identical resolver, or one will rot
        self.assertEqual(extract_locator(BROWSE), extract_locator(BUGSTART))


if __name__ == "__main__":
    unittest.main()
