#!/usr/bin/env python3
"""UserPromptSubmit hook: remind Claude to route coding work on every prompt.

Prints one short line that Claude Code adds to the context. Prints nothing for slash
commands, or when auto-routing is turned off with MODEL_ROUTER_AUTO=0 or "auto": false
in the project's rules file (see rules_file.py). An unreadable rules file counts as
auto-on. Never blocks the prompt.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules_file  # noqa: E402

REMINDER = (
    "model-router: if this request is to build, fix, implement or refactor non-trivial code, "
    "use the model-routing skill and route each task to fast-worker, coder or deep-reasoner. "
    "Skip routing for questions, planning, writing and tiny edits."
)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    prompt = (payload.get("prompt") or "").lstrip()
    if prompt.startswith("/"):
        return  # slash commands carry their own instructions
    try:
        if not rules_file.auto_enabled(rules_file.project_root(payload.get("cwd"))):
            return
    except rules_file.RulesFileError:
        pass  # unreadable rules file: keep the default (on)
    print(REMINDER)


if __name__ == "__main__":
    main()
