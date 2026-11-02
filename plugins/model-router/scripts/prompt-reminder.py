#!/usr/bin/env python3
"""UserPromptSubmit hook: remind Claude to route coding work on every prompt.

Prints one short line that Claude Code adds to the context. Prints nothing for slash
commands, or when auto-routing is turned off with MODEL_ROUTER_AUTO=0 or
"auto": false in the project's rules file. Never blocks the prompt.
"""

import json
import os
import sys
from pathlib import Path

REMINDER = (
    "model-router: if this request is to build, fix, implement or refactor non-trivial code, "
    "use the model-routing skill and route each task to fast-worker, coder or deep-reasoner. "
    "Skip routing for questions, planning, writing and tiny edits."
)


def auto_disabled(cwd: Path) -> bool:
    if os.environ.get("MODEL_ROUTER_AUTO", "").strip().lower() in {"0", "false", "off", "no"}:
        return True
    for name in (".model-router.json", ".claude/model-router.json"):
        path = cwd / name
        if path.is_file():
            try:
                return json.loads(path.read_text()).get("auto") is False
            except (OSError, ValueError, AttributeError):
                return False  # unreadable rules file: keep the default (on)
    return False


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    prompt = (payload.get("prompt") or "").lstrip()
    if prompt.startswith("/"):
        return  # slash commands carry their own instructions
    cwd = Path(payload.get("cwd") or os.getcwd())
    if auto_disabled(cwd):
        return
    print(REMINDER)


if __name__ == "__main__":
    main()
