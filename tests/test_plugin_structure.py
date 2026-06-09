"""Structural / contract tests for the whole plugin.

The skills themselves are prompt text (not unit-testable), but their structure
is: valid manifests, valid frontmatter, folder name == `name`, and the
invocable-vs-internal contract. Catches the kind of drift that breaks loading.

    python3 -m unittest discover -s tests
"""
import json
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"

# skills deliberately marked `user-invocable: false` (helpers Claude calls, not
# user slash-commands). Keep this in sync with the design.
EXPECTED_INTERNAL = {"spec-check", "download-guard", "source-links", "update-investigation",
                     "triage-apply-feedback"}


def parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"{path} has no frontmatter"
    end = text.find("\n---", 4)
    assert end != -1, f"{path} frontmatter not closed"
    data = yaml.safe_load(text[4:end])
    assert isinstance(data, dict), f"{path} frontmatter is not a mapping"
    return data


class TestManifests(unittest.TestCase):
    def test_plugin_json_valid(self):
        d = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
        self.assertEqual(d["name"], "fx-bug-toolkit")
        self.assertIn("description", d)

    def test_marketplace_json_valid(self):
        d = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
        names = [p["name"] for p in d["plugins"]]
        self.assertIn("fx-bug-toolkit", names)


class TestSkills(unittest.TestCase):
    def setUp(self):
        self.skills = sorted(p for p in SKILLS.iterdir() if (p / "SKILL.md").is_file())

    def test_every_skill_has_valid_frontmatter(self):
        for s in self.skills:
            fm = parse_frontmatter(s / "SKILL.md")
            self.assertTrue(fm.get("name"), f"{s.name}: missing name")
            self.assertTrue(fm.get("description"), f"{s.name}: missing description")

    def test_folder_name_matches_frontmatter_name(self):
        # Claude Code uses the folder name as the skill id; keep them in sync.
        for s in self.skills:
            fm = parse_frontmatter(s / "SKILL.md")
            self.assertEqual(fm["name"], s.name, f"{s.name}: name != folder")

    def test_invocable_vs_internal_contract(self):
        internal = set()
        for s in self.skills:
            fm = parse_frontmatter(s / "SKILL.md")
            if fm.get("user-invocable") is False:
                internal.add(s.name)
        self.assertEqual(internal, EXPECTED_INTERNAL)

    def test_every_agent_has_frontmatter_name_matching_filename(self):
        # Claude Code resolves an agent by its frontmatter name; keep it in sync
        # with the filename so `subagent_type` lookups (e.g. firefox-review) work.
        agents = sorted((ROOT / "agents").glob("*.md"))
        self.assertTrue(agents, "no agents found")
        for agent in agents:
            fm = parse_frontmatter(agent)
            self.assertEqual(fm.get("name"), agent.stem,
                             f"{agent.name}: frontmatter name != filename")

    def test_inline_pins_match_versions_manifest(self):
        # `.claude-plugin/versions.json` is the source of truth for pinned deps;
        # the inline pins in skills/ must match it (skill Bash can't read the
        # manifest at runtime). This guards against the "bumped one block,
        # forgot the others" drift the dev loop warns about.
        manifest = json.loads(
            (ROOT / ".claude-plugin" / "versions.json").read_text(encoding="utf-8")
        )
        dash = manifest["firefox-triage-dashboard"]
        bz = manifest["bugzilla-cli"]

        # Triage dashboard: every `REQUIRED="x.y.z"` pin must equal the manifest.
        required_pins = []
        for rel in ("skills/open-triage/SKILL.md", "skills/update/SKILL.md"):
            text = (SKILLS.parent / rel).read_text(encoding="utf-8")
            found = re.findall(r'REQUIRED="([0-9][^"]*)"', text)
            self.assertTrue(found, f"{rel}: no REQUIRED= dashboard pin found")
            required_pins += found
        for v in required_pins:
            self.assertEqual(v, dash, f"dashboard pin {v!r} != versions.json {dash!r}")

        # bugzilla-cli: every `cargo install bugzilla-cli --version X.Y.Z` pin (in
        # /triage's install hint and /update's refresh step) must equal the manifest.
        # (It installs from crates.io now, not `--git …--tag`.)
        bz_tags = []
        for rel in ("skills/triage/SKILL.md", "skills/update/SKILL.md"):
            text = (SKILLS.parent / rel).read_text(encoding="utf-8")
            bz_tags += re.findall(r"bugzilla-cli --version ([0-9]+\.[0-9]+\.[0-9]+)", text)
        self.assertTrue(bz_tags, "no `bugzilla-cli --version …` pin found in the skills")
        for v in bz_tags:
            self.assertEqual(v, bz, f"bugzilla-cli pin v{v} != versions.json v{bz}")

    def test_open_triage_uses_stable_default_port(self):
        # The triage dashboard binds a stable default port so it can be
        # bookmarked (mirrors the viewer's 9000 / Revue's 7779). Guard against a
        # silent regression to the old auto-pick, and never pick a port browsers
        # block as unsafe — e.g. 6000/x11, WHATWG Fetch §port-blocking.
        text = (SKILLS / "open-triage" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('DEFAULT_PORT="${PORT:-9001}"', text,
                      "open-triage must declare the stable default port 9001")
        # browser-blocked ports from the Fetch bad-port list that we must not use.
        for bad in ("6000", "6566", "6665", "6666", "6667", "6668", "6669", "6697"):
            self.assertNotIn(f":-{bad}}}", text,
                             f"{bad} is a browser-blocked port (Fetch §port-blocking)")


if __name__ == "__main__":
    unittest.main()
