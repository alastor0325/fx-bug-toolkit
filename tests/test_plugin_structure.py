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

    def test_agent_has_frontmatter_name(self):
        agent = ROOT / "agents" / "gecko-navigator.md"
        self.assertTrue(agent.is_file())
        fm = parse_frontmatter(agent)
        self.assertEqual(fm.get("name"), "gecko-navigator")


if __name__ == "__main__":
    unittest.main()
