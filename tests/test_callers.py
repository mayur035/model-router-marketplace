import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "plugins" / "model-router" / "scripts"
HOOK = SCRIPTS / "prompt-reminder.py"
INIT = SCRIPTS / "init-config.sh"
UNIVERSAL = ROOT / "universal" / "model-router.py"
DEFAULTS = ROOT / "plugins" / "model-router" / "defaults" / "model-router.json"
sys.path.insert(0, str(SCRIPTS))
import rules_file  # noqa: E402


def clean_env(**extra):
    env = {k: v for k, v in os.environ.items()
           if k not in ("CLAUDE_PROJECT_DIR", "MODEL_ROUTER_AUTO")}
    env.update(extra)
    return env


class PromptReminderTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def run_hook(self, payload, env=None, raw=None):
        stdin = raw if raw is not None else json.dumps(payload)
        r = subprocess.run([sys.executable, str(HOOK)], input=stdin, text=True,
                           capture_output=True, env=env or clean_env(), cwd=self.dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_prints_by_default(self):
        out = self.run_hook({"prompt": "build a thing", "cwd": str(self.dir)})
        self.assertIn("model-router:", out)

    def test_silent_for_slash_command(self):
        self.assertEqual(self.run_hook({"prompt": "/cmd x", "cwd": str(self.dir)}), "")

    def test_silent_when_auto_false(self):
        (self.dir / ".model-router.json").write_text('{"auto": false, "rules": []}')
        self.assertEqual(self.run_hook({"prompt": "build", "cwd": str(self.dir)}), "")

    def test_silent_with_env_off(self):
        out = self.run_hook({"prompt": "build", "cwd": str(self.dir)},
                            env=clean_env(MODEL_ROUTER_AUTO="0"))
        self.assertEqual(out, "")

    def test_malformed_rules_file_still_prints(self):
        (self.dir / ".model-router.json").write_text("{not json")
        out = self.run_hook({"prompt": "build", "cwd": str(self.dir)})
        self.assertIn("model-router:", out)

    def test_malformed_stdin_tolerated(self):
        self.assertIn("model-router:", self.run_hook(None, raw="garbage"))

    def test_project_dir_env_wins_over_cwd(self):
        proj = self.dir / "proj"
        other = self.dir / "other"
        proj.mkdir()
        other.mkdir()
        (proj / ".model-router.json").write_text('{"auto": false}')
        out = self.run_hook({"prompt": "build", "cwd": str(other)},
                            env=clean_env(CLAUDE_PROJECT_DIR=str(proj)))
        self.assertEqual(out, "")


class InitConfigTests(unittest.TestCase):
    def test_created_then_exists(self):
        with tempfile.TemporaryDirectory() as d:
            first = subprocess.run(["bash", str(INIT), d], capture_output=True, text=True,
                                   env=clean_env())
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(first.stdout.strip(), f"created: {Path(d) / '.model-router.json'}")
            second = subprocess.run(["bash", str(INIT), d], capture_output=True, text=True,
                                    env=clean_env())
            self.assertEqual(second.stdout.strip(), f"exists: {Path(d) / '.model-router.json'}")


class UniversalInitTests(unittest.TestCase):
    def run_init(self, d):
        return subprocess.run(
            [sys.executable, str(UNIVERSAL), "init", "opencode", "--project", d],
            capture_output=True, text=True, env=clean_env())

    def test_created_then_kept(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_init(d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(d) / ".model-router.json").is_file())
            self.assertIn("rules:  created .model-router.json with default rules", r.stdout)
            r2 = self.run_init(d)
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertIn("rules:  kept existing .model-router.json", r2.stdout)

    def test_malformed_file_warns_and_keeps(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".model-router.json"
            f.write_text("{oops")
            r = self.run_init(d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("rules:  warning:", r.stdout)
            self.assertEqual(f.read_text(), "{oops")


class DefaultsTests(unittest.TestCase):
    def test_defaults_load_with_auto_true(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / ".model-router.json").write_text(DEFAULTS.read_text())
            rf = rules_file.load(d)
            self.assertIs(rf.auto, True)
            self.assertTrue(rf.rules)


if __name__ == "__main__":
    unittest.main()
