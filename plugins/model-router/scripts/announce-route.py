#!/usr/bin/env python3
"""PreToolUse hook: show the user which model each model-router subagent is launched on.

Prints nothing for other tools or agents, and never blocks the call.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tier_catalog  # noqa: E402

PREFIX = "model-router:"


def default_model(agent_name: str) -> str:
    try:
        tier = tier_catalog.for_agent(agent_name)
    except tier_catalog.TierCatalogError:
        return "unknown"  # announcing is best-effort, never block the agent
    return tier.model if tier else "unknown"


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        return  # malformed hook input; announcing is best-effort, never block the agent
    tool_input = payload.get("tool_input") or {}
    agent_type = tool_input.get("subagent_type") or ""
    if not agent_type.startswith(PREFIX):
        return

    agent_name = agent_type.removeprefix(PREFIX)
    if tool_input.get("model"):
        model = f"{tool_input['model']} (chosen)"
    else:
        model = f"{default_model(agent_name)} (default)"
    task = tool_input.get("description") or "task"
    print(json.dumps({"systemMessage": f"model-router: {task} -> {model} via {agent_name}"}))


if __name__ == "__main__":
    main()
