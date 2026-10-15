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

    def test_profiler_cli_installs_from_npm(self):
        # profiler-cli moved from a git clone + `npm link` that needed a
        # Playwright Firefox to the published @firefox-devtools/profiler-cli
        # package, which has neither requirement.
        for name in ("init", "update"):
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("npm install -g @firefox-devtools/profiler-cli@latest", text,
                          f"{name} must install profiler-cli from npm")
        for s in self.skills:
            text = (s / "SKILL.md").read_text(encoding="utf-8")
            for stale in ("dpalmeiro/profiler-cli", "playwright install firefox"):
                self.assertNotIn(stale, text, f"{s.name}: stale profiler-cli install step")

    def test_profiler_cli_sessions_are_named_and_stopped(self):
        # A profiler-cli session is a daemon that holds the whole profile in
        # memory and never exits on its own, so a skill that loads one must name
        # it and stop it.
        for s in self.skills:
            text = (s / "SKILL.md").read_text(encoding="utf-8")
            if "profiler-cli load" not in text:
                continue
            self.assertIsNone(re.search(r"profiler-cli load <url>(?! --session)", text),
                              f"{s.name}: profiler-cli load without --session")
            self.assertIsNotNone(re.search(r"profiler-cli stop\s+--session <id>", text),
                                 f"{s.name}: loads a profiler-cli session but never stops it")

    def test_triage_comments_follow_ste100(self):
        # Every comment /triage drafts for Bugzilla follows ASD-STE100, and the
        # refine skill re-drafts under the same standard.
        for name in ("triage", "triage-apply-feedback"):
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("ASD-STE100", text, f"{name}: no ASD-STE100 writing standard")
            self.assertIn("20 words max", text, f"{name}: no instruction length limit")
            self.assertIn("Could you please", text, f"{name}: no polite-request rule for named people")

    def test_bug_start_security_approval_section(self):
        # A security bug's investigation carries the sec-approval answers, and
        # its affected-versions part names every supported channel by number.
        text = (SKILLS / "bug-start" / "SKILL.md").read_text(encoding="utf-8")
        start = text.index("**Required Document Structure")
        end = text.index("### After Creating Investigation File")
        template = text[start:end]
        self.assertIn("## Security Approval", template, "bug-start: Security Approval not in the deep template")
        self.assertIn("### Affected versions", template, "bug-start: no Affected versions part in the template")
        for row in ("| Nightly |", "| Beta |", "| Release |", "| ESR {NNN} |", "| ESR {MMM} |"):
            self.assertIn(row, template, f"bug-start: affected-versions table lacks {row}")
        self.assertIn("unverified", template, "bug-start: no fallback verdict for an unchecked branch")
        self.assertIn("status-firefox-esrNNN", template, "bug-start: ESR status-flag form missing")
        self.assertIn("which bug introduced the flaw", template, "bug-start: sec-approval questions missing")
        self.assertIsNone(re.search(r"<https?://", template),
                          "bug-start: <url> links break the skill's own link checker")
        self.assertIn("is the `## Security Approval` section present", text,
                      "bug-start: self-check item for Security Approval missing")
        self.assertIn("- ❌ `## Security Approval`", text,
                      "bug-start: triage mode must omit the Security Approval section")
        update = (SKILLS / "update-investigation" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("Security Approval", update, "update-investigation: no mapping for Security Approval")


# The skills the gecko-triage Hackbot agent runs in its cloud container.
HACKBOT_SKILLS = ("analyze-profile", "bug-start", "check-log", "spec-check")
# Tools the container does not have. A Hackbot-mode line may name one only to
# skip or replace it, never as something to run.
HACKBOT_FORBIDDEN = (
    r"bmo-to-md", r"BMO_API_KEY", r"searchfox-cli", r"bugzilla-cli", r"mcp__moz__",
    r"gecko-navigator", r"\bjj\b", r"\bmach\b", r"\bnpm\b", r"(?<![\w-])/update\b",
    r"firefox-wiki", r"\.fx-bug-toolkit", r"/rename\b", r"\bviewer\b", r"TaskCreate",
    r"AskUserQuestion", r"/download-guard", r"/analyze-profile",
)
# The MCP tools the container provides.
HACKBOT_MCP_TOOLS = {
    "mcp__bugzilla__search_bugs", "mcp__bugzilla__get_bugs",
    "mcp__bugzilla__get_bug_comments", "mcp__bugzilla__get_bug_attachments",
    "mcp__searchfox__search_identifier", "mcp__searchfox__search_text",
    "mcp__searchfox__find_definition", "mcp__searchfox__get_function_at_line",
    "mcp__searchfox__get_blame", "mcp__searchfox__get_file",
    "mcp__mozilla_vcs__file_history", "mcp__mozilla_vcs__get_commit_info",
    "mcp__mozilla_vcs__get_commit_diff", "mcp__attachments__fetch_attachment",
}


def hackbot_section(text: str):
    """The line number and body of the `## Hackbot mode` section, up to the next heading or rule."""
    start = text.index("\n## Hackbot mode\n")
    ends = [i for i in (text.find("\n## ", start + 1), text.find("\n---\n", start)) if i != -1]
    return text.count("\n", 0, start) + 1, text[start:min(ends, default=len(text))]


def hackbot_violations(section: str) -> list:
    """Lines that name a forbidden tool other than to skip or replace it."""
    bad = []
    for line in section.splitlines():
        if re.match(r"- (Skip|Never)\b", line):
            continue
        if line.startswith("- Instead of ") and ":" in line:
            line = line.split(":", 1)[1]
        if any(re.search(p, line) for p in HACKBOT_FORBIDDEN):
            bad.append(line.strip())
    return bad


class TestHackbotMode(unittest.TestCase):
    def section(self, name):
        return hackbot_section((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))[1]

    def test_every_hackbot_skill_has_the_section_near_its_top(self):
        for name in HACKBOT_SKILLS:
            text = (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")
            self.assertEqual(text.count("\n## Hackbot mode\n"), 1, f"{name}: needs one Hackbot mode section")
            line, section = hackbot_section(text)
            self.assertLess(line, 30, f"{name}: Hackbot mode section is not near the top")
            self.assertIn("printenv FX_BUG_TOOLKIT_MODE", section, f"{name}: no env-var check")
            self.assertIn("`hackbot`", section, f"{name}: no mode value")
            self.assertIn("skill runs as written", section,
                          f"{name}: does not say local behavior is unchanged")
            self.assertIn("Never ask a question", section, f"{name}: may ask in an unattended run")
            self.assertNotIn("```", section, f"{name}: Hackbot mode must not carry a command block")

    def test_hackbot_section_runs_no_forbidden_tool(self):
        for name in HACKBOT_SKILLS:
            self.assertEqual(hackbot_violations(self.section(name)), [],
                             f"{name}: Hackbot mode tells the agent to run a local-only tool")

    def test_hackbot_section_names_only_provided_mcp_tools(self):
        for name in HACKBOT_SKILLS:
            for tool in re.findall(r"mcp__\w+", self.section(name)):
                if not tool.startswith("mcp__moz__"):
                    self.assertIn(tool, HACKBOT_MCP_TOOLS, f"{name}: {tool} is not in the container")

    def test_hackbot_violations_catches_a_forbidden_tool(self):
        self.assertEqual(hackbot_violations("- Instead of `jj log`: run `searchfox-cli`."),
                         ["run `searchfox-cli`."])
        self.assertEqual(hackbot_violations("- Run `bmo-to-md 1`."), ["- Run `bmo-to-md 1`."])
        self.assertEqual(hackbot_violations("- Skip `./mach wpt-update`."), [])
        self.assertEqual(hackbot_violations("- Never use AskUserQuestion."), [])
        self.assertEqual(hackbot_violations("- Instead of `jj log`: use file history."), [])

    def test_hackbot_section_covers_each_skills_gaps(self):
        expected = {
            "bug-start": ("mcp__bugzilla__get_bugs", "mcp__bugzilla__get_bug_comments",
                          "**Public: Yes**", "mcp__mozilla_vcs__file_history",
                          "Searchfox revision that the task gives", "$FX_BUG_INVESTIGATION_DIR",
                          "Accept any component", "link check", "lock file", "history log"),
            "check-log": (".moz_log", "mcp__attachments__fetch_attachment", "log-analysis.log"),
            "spec-check": ("mcp__searchfox__search_text", "wpt-update", "report it in your answer",
                           "Security Rules still apply"),
            "analyze-profile": ("tooling gap", "Never install or update", "wiki"),
        }
        for name, needles in expected.items():
            section = self.section(name)
            for needle in needles:
                self.assertIn(needle, section, f"{name}: Hackbot mode lacks {needle!r}")


if __name__ == "__main__":
    unittest.main()
