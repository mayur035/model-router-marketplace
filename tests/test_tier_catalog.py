import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "model-router" / "scripts"
ANNOUNCE = SCRIPTS / "announce-route.py"
UNIVERSAL = ROOT / "universal" / "model-router.py"
sys.path.insert(0, str(SCRIPTS))
import tier_catalog  # noqa: E402


class RealCatalogTests(unittest.TestCase):
    def test_tiers_match_the_shipped_agents(self):
        found = tier_catalog.tiers()
        self.assertEqual(list(found), ["fast", "standard", "deep"])
        self.assertEqual((found["fast"].agent, found["fast"].model), ("fast-worker", "haiku"))
        self.assertEqual((found["standard"].agent, found["standard"].model), ("coder", "sonnet"))
        self.assertEqual((found["deep"].agent, found["deep"].model), ("deep-reasoner", "opus"))
        self.assertEqual(found["standard"].tier, "standard")
        self.assertIn("standard implementation work", found["standard"].description)
        self.assertIn("ESCALATE:", found["standard"].body)
        self.assertTrue(found["standard"].body.endswith("\n"))
        self.assertFalse(found["standard"].body.endswith("\n\n"))
        self.assertFalse(found["standard"].body.startswith("---"))


def agent_file(name, model="haiku", description="Does things", body="Do it.", eol="\n"):
    lines = ["---", f"name: {name}"]
    lines.append(f"description: {description}")
    if model:
        lines.append(f"model: {model}")
    lines += ["---", body, ""]
    return eol.join(lines)


class TempCatalogTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write_all(self, **overrides):
        """Write the three tier agents, one file each, named like the agent."""
        for agent, model in (("fast-worker", "haiku"), ("coder", "sonnet"),
                             ("deep-reasoner", "opus")):
            (self.dir / f"{agent}.md").write_text(
                overrides.get(agent) or agent_file(agent, model))

    def test_tier_agent_without_model_is_an_error_naming_the_tier(self):
        self.write_all(coder=agent_file("coder", model=None))
        with self.assertRaises(tier_catalog.TierCatalogError) as caught:
            tier_catalog.tiers(self.dir)
        self.assertIn("standard", str(caught.exception))

    def test_crlf_agent_files_parse_cleanly(self):
        self.write_all(coder=agent_file("coder", "sonnet", "Std work", "Line one.", eol="\r\n"))
        coder = tier_catalog.tiers(self.dir)["standard"]
        self.assertEqual((coder.model, coder.description), ("sonnet", "Std work"))
        self.assertEqual(coder.body, "Line one.\n")

    def test_for_agent_accepts_bare_and_prefixed_names(self):
        self.write_all()
        bare = tier_catalog.for_agent("coder", self.dir)
        self.assertEqual((bare.tier, bare.model), ("standard", "sonnet"))
        self.assertEqual(tier_catalog.for_agent("model-router:coder", self.dir), bare)

    def test_unknown_agent_is_none(self):
        self.write_all()
        self.assertIsNone(tier_catalog.for_agent("nope", self.dir))

    def test_extra_non_tier_agent_is_ignored(self):
        self.write_all()
        (self.dir / "reviewer.md").write_text(agent_file("reviewer", "opus"))
        self.assertEqual(list(tier_catalog.tiers(self.dir)), ["fast", "standard", "deep"])
        self.assertIsNone(tier_catalog.for_agent("reviewer", self.dir))

    def test_name_field_decides_identity_not_filename(self):
        self.write_all(coder="")
        (self.dir / "coder.md").unlink()
        (self.dir / "whatever.md").write_text(agent_file("coder", "sonnet"))
        self.assertEqual(tier_catalog.tiers(self.dir)["standard"].model, "sonnet")
        self.assertIsNotNone(tier_catalog.for_agent("coder", self.dir))


class AnnounceRouteTests(unittest.TestCase):
    def announce(self, tool_input):
        done = subprocess.run([sys.executable, str(ANNOUNCE)], input=json.dumps(
            {"tool_input": tool_input}), capture_output=True, text=True, check=True)
        return json.loads(done.stdout)["systemMessage"] if done.stdout.strip() else None

    def test_default_model_comes_from_the_tier_agent(self):
        message = self.announce({"subagent_type": "model-router:coder", "description": "x"})
        self.assertIn("sonnet (default)", message)

    def test_chosen_model_wins(self):
        message = self.announce(
            {"subagent_type": "model-router:coder", "description": "x", "model": "opus"})
        self.assertIn("opus (chosen)", message)

    def test_unknown_model_router_agent_is_unknown(self):
        message = self.announce({"subagent_type": "model-router:nope", "description": "x"})
        self.assertIn("unknown (default)", message)

    def test_other_agents_are_not_announced(self):
        self.assertIsNone(self.announce({"subagent_type": "Explore", "description": "x"}))


class UniversalInitTests(unittest.TestCase):
    def test_opencode_agent_carries_description_and_body_from_the_coder_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run([sys.executable, str(UNIVERSAL), "init", "opencode", "--project", tmp],
                           capture_output=True, text=True, check=True)
            written = (Path(tmp) / ".opencode" / "agents" / "coder.md").read_text()
        self.assertIn("Use for standard implementation work routed by model-router - features",
                      written)
        self.assertNotIn("by the model-router skill", written)
        self.assertIn("You are a solid implementation engineer.", written)
        self.assertIn("ESCALATE: tests still failing", written)


if __name__ == "__main__":
    unittest.main()
