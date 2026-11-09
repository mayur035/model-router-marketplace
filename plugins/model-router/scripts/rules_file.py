#!/usr/bin/env python3
"""Locate, create, load and maintain the model-router rules file (.model-router.json)."""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

_NAME = ".model-router.json"
_LEGACY = Path(".claude") / "model-router.json"
_DEFAULTS = Path(__file__).resolve().parent.parent / "defaults" / "model-router.json"
_OFF = {"0", "false", "off", "no"}
_TIERS = {"fast", "standard", "deep"}


class RulesFileError(Exception):
    pass


@dataclass(frozen=True)
class RulesFile:
    path: Path
    rules: list[dict]
    auto: bool
    about: str | None


def project_root(hook_cwd: str | None = None) -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR") or hook_cwd or os.getcwd())


def locate(root) -> Path | None:
    root = Path(root)
    for p in (root / _NAME, root / _LEGACY):
        if p.is_file():
            return p
    return None


def ensure(root) -> tuple[Path, bool]:
    root = Path(root)
    found = locate(root)
    if found:
        return found, False
    target = root / _NAME
    target.write_text(_DEFAULTS.read_text(encoding="utf-8"), encoding="utf-8")
    return target, True


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as e:
        raise RulesFileError(f"cannot read {path}: {e}") from e
    except json.JSONDecodeError as e:
        raise RulesFileError(f"invalid JSON in {path}: {e}") from e
    if not isinstance(data, dict):
        raise RulesFileError(f"{path}: top level must be an object")
    return data


def _parse(path: Path, data: dict) -> RulesFile:
    rules = data.get("rules", [])
    if not isinstance(rules, list):
        raise RulesFileError(f"{path}: 'rules' must be a list")
    auto = data.get("auto", True)
    if not isinstance(auto, bool):
        raise RulesFileError(f"{path}: 'auto' must be true or false")
    about = data.get("about")
    return RulesFile(path, rules, auto, about if isinstance(about, str) else None)


def load(root) -> RulesFile | None:
    path = locate(root)
    if path is None:
        return None
    return _parse(path, _read(path))


def auto_enabled(root) -> bool:
    if os.environ.get("MODEL_ROUTER_AUTO", "").strip().lower() in _OFF:
        return False
    rf = load(root)
    return True if rf is None else rf.auto


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _defaults_data() -> dict:
    return json.loads(_DEFAULTS.read_text(encoding="utf-8"))


def _cmd_show(root: Path) -> int:
    rf = load(root)
    if rf is None:
        print(f"no rules file in {root}")
        return 1
    print(f"Rules file: {rf.path}")
    print(f"Auto-routing: {'on' if rf.auto else 'off'}")
    print()
    print("| When | Tier or model |")
    print("|---|---|")
    for r in rf.rules:
        r = r if isinstance(r, dict) else {}
        when = str(r.get("when", "-")).replace("|", "\\|")
        print(f"| {when} | {r.get('tier') or r.get('model') or '-'} |")
    return 0


def _cmd_reset(root: Path) -> int:
    found = locate(root)
    target = root / _NAME
    _write(target, _defaults_data())
    if found is not None and found != target:
        found.unlink()
        print(f"reset: {target} (moved from .claude/model-router.json)")
    else:
        print(f"reset: {target}")
    return 0


def _cmd_clear(root: Path) -> int:
    path = locate(root)
    if path is None:
        print(f"error: no rules file in {root}")
        return 1
    data = _read(path)
    _parse(path, data)
    data["rules"] = []
    _write(path, data)
    print(f"cleared: {path}")
    return 0


def _cmd_check(root: Path) -> int:
    rf = load(root)
    if rf is None:
        print(f"error: no rules file in {root}")
        return 1
    print(f"ok: {rf.path}")
    for i, r in enumerate(rf.rules, 1):
        if not isinstance(r, dict):
            print(f"warning: rule {i} is not an object")
            continue
        when = r.get("when")
        if not isinstance(when, str) or not when.strip():
            print(f"warning: rule {i} has a missing or empty 'when'")
        if "tier" not in r and "model" not in r:
            print(f"warning: rule {i} has neither 'tier' nor 'model'")
        elif "tier" in r and (not isinstance(r["tier"], str) or r["tier"] not in _TIERS):
            print(f"warning: rule {i} has unknown tier {r['tier']!r} (use fast, standard or deep)")
    return 0


def main(argv: list[str]) -> int:
    verbs = ("ensure", "show", "reset", "clear", "check")
    if not argv or argv[0] not in verbs:
        print(f"usage: rules_file.py <{'|'.join(verbs)}> [PROJECT_DIR]", file=sys.stderr)
        return 2
    verb = argv[0]
    root = Path(argv[1]) if len(argv) > 1 else project_root()
    try:
        if verb == "ensure":
            path, created = ensure(root)
            print(f"{'created' if created else 'exists'}: {path}")
            return 0
        return {"show": _cmd_show, "reset": _cmd_reset, "clear": _cmd_clear, "check": _cmd_check}[verb](root)
    except (RulesFileError, OSError) as e:
        print(f"error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
