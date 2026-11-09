import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "plugins" / "model-router" / "scripts" / "rules_file.py"
sys.path.insert(0, str(SCRIPT.parent))
import rules_file as rf  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("CLAUDE_PROJECT_DIR", None)
        os.environ.pop("MODEL_ROUTER_AUTO", None)

    @property
    def current(self):
        return self.root / ".model-router.json"

    @property
    def legacy(self):
        return self.root / ".claude" / "model-router.json"

    def put(self, path, data):
        path.parent.mkdir(exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data))

    def cli(self, *args):
        p = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                           text=True, env=os.environ.copy())
        return p.returncode, p.stdout


class ProjectRootTest(Base):
    def test_env_wins(self):
        os.environ["CLAUDE_PROJECT_DIR"] = "/env"
        self.assertEqual(rf.project_root("/hook"), Path("/env"))

    def test_hook_cwd_when_env_empty(self):
        os.environ["CLAUDE_PROJECT_DIR"] = ""
        self.assertEqual(rf.project_root("/hook"), Path("/hook"))

    def test_falls_back_to_cwd(self):
        self.assertEqual(rf.project_root(), Path(os.getcwd()))


class LocateEnsureTest(Base):
    def test_none(self):
        self.assertIsNone(rf.locate(self.root))

    def test_legacy_only(self):
        self.put(self.legacy, {})
        self.assertEqual(rf.locate(self.root), self.legacy)

    def test_current_wins(self):
        self.put(self.legacy, {})
        self.put(self.current, {})
        self.assertEqual(rf.locate(self.root), self.current)

    def test_ensure_creates_defaults(self):
        path, created = rf.ensure(self.root)
        self.assertEqual((path, created), (self.current, True))
        self.assertTrue(json.loads(self.current.read_text())["rules"])
        self.assertEqual(rf.ensure(self.root), (self.current, False))

    def test_ensure_keeps_legacy_and_malformed(self):
        self.put(self.legacy, "{not json")
        self.assertEqual(rf.ensure(self.root), (self.legacy, False))
        self.assertFalse(self.current.exists())
        self.assertEqual(self.legacy.read_text(), "{not json")


class LoadTest(Base):
    def test_no_file(self):
        self.assertIsNone(rf.load(self.root))

    def test_defaults_applied(self):
        self.put(self.current, {})
        r = rf.load(self.root)
        self.assertEqual((r.path, r.rules, r.auto, r.about), (self.current, [], True, None))

    def test_values(self):
        self.put(self.current, {"rules": [{"when": "x", "tier": "fast"}], "auto": False, "about": "hi"})
        r = rf.load(self.root)
        self.assertEqual((r.rules, r.auto, r.about), ([{"when": "x", "tier": "fast"}], False, "hi"))

    def test_errors(self):
        for bad in ("{oops", "[]", '{"rules": {}}', '{"auto": "yes"}'):
            with self.subTest(bad=bad):
                self.put(self.current, bad)
                with self.assertRaises(rf.RulesFileError):
                    rf.load(self.root)

    def test_unreadable(self):
        self.current.mkdir()  # exists but is a directory: locate ignores it
        self.assertIsNone(rf.load(self.root))
        self.current.rmdir()
        self.current.write_bytes(b"\xff\xfe\x00")
        with self.assertRaises(rf.RulesFileError):
            rf.load(self.root)


class AutoEnabledTest(Base):
    def test_default_true(self):
        self.assertTrue(rf.auto_enabled(self.root))

    def test_file_false(self):
        self.put(self.current, {"auto": False})
        self.assertFalse(rf.auto_enabled(self.root))

    def test_env_override(self):
        self.put(self.current, {"auto": True})
        for v in ("0", "false", " OFF ", "No"):
            with self.subTest(v=v):
                os.environ["MODEL_ROUTER_AUTO"] = v
                self.assertFalse(rf.auto_enabled(self.root))
        os.environ["MODEL_ROUTER_AUTO"] = "1"
        self.assertTrue(rf.auto_enabled(self.root))

    def test_error_propagates(self):
        self.put(self.current, "{oops")
        with self.assertRaises(rf.RulesFileError):
            rf.auto_enabled(self.root)


class CliTest(Base):
    def test_ensure(self):
        code, out = self.cli("ensure", str(self.root))
        self.assertEqual((code, out), (0, f"created: {self.current}\n"))
        self.assertEqual(self.cli("ensure", str(self.root)), (0, f"exists: {self.current}\n"))

    def test_project_dir_defaults_to_env(self):
        os.environ["CLAUDE_PROJECT_DIR"] = str(self.root)
        self.assertEqual(self.cli("ensure")[1], f"created: {self.current}\n")

    def test_show(self):
        self.put(self.current, {"auto": False, "rules": [
            {"when": "a", "tier": "deep"}, {"when": "b", "model": "opus"}, {"when": "c"}]})
        code, out = self.cli("show", str(self.root))
        self.assertEqual(code, 0)
        self.assertEqual(out, f"Rules file: {self.current}\nAuto-routing: off\n\n"
                              "| When | Tier or model |\n|---|---|\n| a | deep |\n| b | opus |\n| c | - |\n")

    def test_show_missing_and_error(self):
        self.assertEqual(self.cli("show", str(self.root)), (1, f"no rules file in {self.root}\n"))
        self.put(self.current, "[]")
        code, out = self.cli("show", str(self.root))
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("error: "))

    def test_reset_plain(self):
        self.put(self.current, {"rules": []})
        self.assertEqual(self.cli("reset", str(self.root)), (0, f"reset: {self.current}\n"))
        self.assertTrue(json.loads(self.current.read_text())["rules"])

    def test_reset_no_file(self):
        self.assertEqual(self.cli("reset", str(self.root)), (0, f"reset: {self.current}\n"))
        self.assertTrue(self.current.exists())

    def test_reset_from_legacy(self):
        self.put(self.legacy, {"rules": []})
        code, out = self.cli("reset", str(self.root))
        self.assertEqual((code, out), (0, f"reset: {self.current} (moved from .claude/model-router.json)\n"))
        self.assertFalse(self.legacy.exists())
        self.assertTrue(self.current.exists())

    def test_clear_preserves_other_keys(self):
        self.put(self.current, {"about": "x", "auto": False, "extra": 1, "rules": [{"when": "a", "tier": "fast"}]})
        self.assertEqual(self.cli("clear", str(self.root)), (0, f"cleared: {self.current}\n"))
        text = self.current.read_text()
        self.assertTrue(text.endswith("}\n"))
        self.assertEqual(json.loads(text), {"about": "x", "auto": False, "extra": 1, "rules": []})

    def test_clear_errors(self):
        self.assertEqual(self.cli("clear", str(self.root))[0], 1)
        self.put(self.current, "{oops")
        code, out = self.cli("clear", str(self.root))
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("error: "))
        self.assertEqual(self.current.read_text(), "{oops")

    def test_check_ok_and_warnings(self):
        self.put(self.current, {"rules": [
            {"when": "a", "tier": "fast"}, "junk", {"tier": "deep"},
            {"when": "d"}, {"when": "e", "tier": "huge"}]})
        code, out = self.cli("check", str(self.root))
        self.assertEqual(code, 0)
        lines = out.splitlines()
        self.assertEqual(lines[0], f"ok: {self.current}")
        for n in (2, 3, 4, 5):
            self.assertTrue(any(l.startswith(f"warning: rule {n} ") for l in lines), n)
        self.assertFalse(any(l.startswith("warning: rule 1 ") for l in lines))

    def test_check_errors(self):
        self.assertEqual(self.cli("check", str(self.root))[0], 1)
        self.put(self.current, '{"auto": 1}')
        code, out = self.cli("check", str(self.root))
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("error: "))

    def test_check_warns_on_non_string_tier(self):
        self.put(self.current, {"rules": [{"when": "a", "tier": ["fast"]}]})
        code, out = self.cli("check", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("warning: rule 1 ", out)

    def test_ensure_on_missing_dir_is_an_error_not_a_traceback(self):
        code, out = self.cli("ensure", str(self.root / "nope"))
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("error: "), out)


if __name__ == "__main__":
    unittest.main()
