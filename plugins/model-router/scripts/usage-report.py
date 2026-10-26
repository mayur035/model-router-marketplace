#!/usr/bin/env python3
"""Per-model token usage for a Claude Code session, with proof of which model answered.

Reads the session transcript and its subagent transcripts. The `model` on each
response is reported by the API, so it shows the model that actually ran, not
the one that was requested.

Usage: usage-report.py [--last] [session.jsonl]
  session.jsonl  default: the newest session for the cwd
  --last         only the most recent routed run: from the last /route or model-routing
                 skill invocation to the end of the session
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
TOKEN_FIELDS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
                "output_tokens")
FAMILIES = ("haiku", "sonnet", "opus", "fable")
ROUTE_COMMAND = "<command-name>/model-router:route</command-name>"
ROUTE_SKILL = "model-router:model-routing"


def find_session(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    project_dir = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-",
                                                                str(Path.cwd()))
    sessions = sorted(project_dir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not sessions:
        sys.exit(f"No session transcripts found in {project_dir}")
    return sessions[-1]


def expected_models() -> dict[str, str]:
    """agentType -> model declared in this plugin's agent frontmatter."""
    expected = {}
    for agent_file in (PLUGIN_ROOT / "agents").glob("*.md"):
        text = agent_file.read_text()
        name = re.search(r"^name:\s*(\S+)", text, re.M)
        model = re.search(r"^model:\s*(\S+)", text, re.M)
        if name and model:
            expected[f"model-router:{name.group(1)}"] = model.group(1)
    return expected


def read_entries(transcript: Path) -> list[dict]:
    entries = []
    for line in transcript.open():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a partially written last line while the session is live
    return entries


def tool_uses(entry: dict) -> list[dict]:
    content = (entry.get("message") or {}).get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if block.get("type") == "tool_use"]


def last_route_start(entries: list[dict]) -> int | None:
    """Index of the last /route command or model-routing skill call, if any."""
    start = None
    for index, entry in enumerate(entries):
        if entry.get("type") == "user" and ROUTE_COMMAND in json.dumps(entry.get("message")):
            start = index
        for block in tool_uses(entry):
            if (block.get("input") or {}).get("skill") == ROUTE_SKILL:
                start = index
    return start


def agent_launches(entries: list[dict]) -> dict[str, str | None]:
    """Agent tool_use id -> `model` passed on that call (None when the agent's default was used)."""
    return {block["id"]: (block.get("input") or {}).get("model")
            for entry in entries for block in tool_uses(entry)
            if (block.get("input") or {}).get("subagent_type")}


def read_usage(entries: list[dict]) -> tuple[dict[str, dict[str, int]], int]:
    """Token totals per model. A response is logged once per content block, so dedupe by id."""
    responses = {}
    for entry in entries:
        message = entry.get("message") or {}
        if entry.get("type") != "assistant" or not message.get("usage"):
            continue
        if message.get("model") == "<synthetic>":
            continue
        responses[message.get("id") or id(entry)] = (message["model"], message["usage"])

    totals: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(TOKEN_FIELDS, 0))
    for model, usage in responses.values():
        for field in TOKEN_FIELDS:
            totals[model][field] += usage.get(field) or 0
    return totals, len(responses)


def family(model: str) -> str:
    return next((f for f in FAMILIES if f in model), model)


def fmt(n: int) -> str:
    return f"{n:,}"


def main() -> None:
    args = sys.argv[1:]
    last_only = "--last" in args
    paths = [arg for arg in args if arg != "--last"]
    session = find_session(paths[0] if paths else None)
    expected = expected_models()

    entries = read_entries(session)
    scope = "whole session"
    if last_only:
        start = last_route_start(entries)
        if start is None:
            scope = "whole session (no /route run found for --last)"
        else:
            entries = entries[start:]
            scope = "last routed run only"
    launches = agent_launches(entries)

    runs = [("main session", "-", "main", "", entries)]
    for transcript in sorted((session.parent / session.stem / "subagents").glob("*.jsonl")):
        meta_file = transcript.with_suffix(".meta.json")
        meta = json.loads(meta_file.read_text()) if meta_file.exists() else {}
        tool_use_id = meta.get("toolUseId")
        if last_only and tool_use_id not in launches:
            continue
        agent_type = meta.get("agentType", "unknown")
        if launches.get(tool_use_id):
            requested, source = launches[tool_use_id], " (chosen)"
        else:
            requested, source = expected.get(agent_type, "-"), " (default)"
        runs.append((meta.get("description", transcript.stem), agent_type, requested,
                     source if requested != "-" else "", read_entries(transcript)))

    print(f"Session: {session}")
    print(f"Scope: {scope}\n")
    print("## Proof: requested vs. actual model\n")
    print("| Task | Agent | Requested | Actual (from API) | Responses | Check |")
    print("|---|---|---|---|---|---|")
    by_model: dict[str, dict[str, int]] = defaultdict(lambda: dict.fromkeys(TOKEN_FIELDS, 0))
    for task, agent_type, requested, source, run_entries in runs:
        totals, count = read_usage(run_entries)
        for model, tokens in totals.items():
            for field in TOKEN_FIELDS:
                by_model[model][field] += tokens[field]
        actual = ", ".join(sorted(totals)) or "-"
        if requested in ("-", "main") or not totals:
            check = "-"
        elif all(family(m) == family(requested) for m in totals):
            check = "OK"
        else:
            check = "MISMATCH"
        print(f"| {task} | {agent_type} | {requested}{source} | {actual} | {count} | {check} |")

    print("\n## Tokens by model\n")
    print("| Model | Input | Cache write | Cache read | Output | Total |")
    print("|---|---|---|---|---|---|")
    grand = dict.fromkeys(TOKEN_FIELDS, 0)
    for model in sorted(by_model):
        tokens = by_model[model]
        for field in TOKEN_FIELDS:
            grand[field] += tokens[field]
        print(f"| {model} | " + " | ".join(fmt(tokens[f]) for f in TOKEN_FIELDS)
              + f" | {fmt(sum(tokens.values()))} |")
    print("| **All** | " + " | ".join(fmt(grand[f]) for f in TOKEN_FIELDS)
          + f" | {fmt(sum(grand.values()))} |")


if __name__ == "__main__":
    main()
