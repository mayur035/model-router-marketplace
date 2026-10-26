#!/usr/bin/env python3
"""Set up model-router in a project for Cursor, Codex CLI, Gemini CLI or OpenCode.

Writes three subagents (fast, standard, deep tier), each pinned to a model, plus a routing
section in the tool's instructions file that tells the main agent how to delegate. Claude Code
uses the plugin in plugins/model-router instead.

Usage:
  model-router.py init <tool> [--project DIR] [--fast MODEL] [--standard MODEL] [--deep MODEL]
                              [--force]
  model-router.py tools
"""

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "plugins" / "model-router"
ROUTING_TEMPLATE = Path(__file__).resolve().parent / "ROUTING.md"
RULES_FILE = ".model-router.json"
LEGACY_RULES_FILE = ".claude/model-router.json"
BLOCK_START = "<!-- model-router:{tool}:start -->"
BLOCK_END = "<!-- model-router:{tool}:end -->"
TIERS = ("fast", "standard", "deep")
TIER_SOURCE = {"fast": "fast-worker", "standard": "coder", "deep": "deep-reasoner"}


@dataclass(frozen=True)
class Tool:
    label: str
    agents_dir: str
    extension: str
    instructions_file: str
    delegate_hint: str
    find_models: str
    default_models: dict[str, str] | None = None
    underscore_names: bool = False


TOOLS = {
    "cursor": Tool(
        label="Cursor",
        agents_dir=".cursor/agents",
        extension=".md",
        instructions_file="AGENTS.md",
        delegate_hint="Delegate to the subagent by name, e.g. `/coder add the endpoint`.",
        find_models="run `cursor-agent models` (signed in) or check Cursor's model picker",
    ),
    "codex": Tool(
        label="Codex CLI",
        agents_dir=".codex/agents",
        extension=".toml",
        instructions_file="AGENTS.md",
        delegate_hint="Spawn the custom agent by name, e.g. `have coder add the endpoint`.",
        find_models="check the models your Codex account offers (the model picker in Codex)",
        underscore_names=True,
    ),
    "gemini": Tool(
        label="Gemini CLI",
        agents_dir=".gemini/agents",
        extension=".md",
        instructions_file="GEMINI.md",
        delegate_hint="Call the subagent's tool, which has the same name as the subagent.",
        find_models="check the models your Gemini CLI account offers (the model picker in Gemini CLI)",
    ),
    "opencode": Tool(
        label="OpenCode",
        agents_dir=".opencode/agents",
        extension=".md",
        instructions_file="AGENTS.md",
        delegate_hint="Use the Task tool with the subagent's name.",
        find_models="run `opencode models`",
        default_models={
            "fast": "anthropic/claude-haiku-5-5",
            "standard": "anthropic/claude-sonnet-5-5",
            "deep": "anthropic/claude-opus-5-5",
        },
    ),
}


def read_source_agent(tier: str) -> tuple[str, str]:
    """(description, instructions) from the Claude Code plugin's agent file for this tier."""
    text = (PLUGIN_ROOT / "agents" / f"{TIER_SOURCE[tier]}.md").read_text()
    match = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    if not match:
        sys.exit(f"Unreadable agent file for tier {tier}")
    frontmatter, body = match.groups()
    description = re.search(r"^description:\s*(.+)$", frontmatter, re.M).group(1)
    description = description.replace("by the model-router skill", "by model-router")
    return description.strip(), body.strip() + "\n"


def agent_name(tool: Tool, tier: str) -> str:
    name = TIER_SOURCE[tier]
    return name.replace("-", "_") if tool.underscore_names else name


def render_agent(tool_key: str, name: str, description: str, model: str, body: str) -> str:
    quote = json.dumps  # JSON strings are valid YAML and TOML basic strings
    if tool_key == "codex":
        return (f"name = {quote(name)}\ndescription = {quote(description)}\n"
                f"model = {quote(model)}\ndeveloper_instructions = '''\n{body}'''\n")
    fields = {
        "cursor": [("name", name), ("description", description), ("model", model)],
        "gemini": [("name", name), ("description", description), ("kind", "local"),
                   ("model", model)],
        "opencode": [("description", description), ("mode", "subagent"), ("model", model)],
    }[tool_key]
    frontmatter = "\n".join(f"{key}: {quote(value)}" for key, value in fields)
    return f"---\n{frontmatter}\n---\n{body}"


def existing_model(path: Path) -> str | None:
    match = re.search(r'^model\s*[:=]\s*"([^"]*)"', path.read_text(), re.M)
    return match.group(1) if match else None


def render_block(tool_key: str, tool: Tool, names: dict[str, str],
                 models: dict[str, str]) -> str:
    routing = ROUTING_TEMPLATE.read_text().format(
        tool=tool.label, fast=names["fast"], standard=names["standard"], deep=names["deep"],
        fast_model=models["fast"], standard_model=models["standard"],
        deep_model=models["deep"], delegate_hint=tool.delegate_hint,
    )
    start, end = BLOCK_START.format(tool=tool_key), BLOCK_END.format(tool=tool_key)
    return f"{start}\n{routing.strip()}\n{end}\n"


def upsert_block(path: Path, tool_key: str, block: str) -> str:
    if not path.exists():
        path.write_text(block)
        return "created"
    text = path.read_text()
    start, end = BLOCK_START.format(tool=tool_key), BLOCK_END.format(tool=tool_key)
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end) + r"\n?", re.S)
    if pattern.search(text):
        path.write_text(pattern.sub(lambda _: block, text, count=1))
        return "updated"
    path.write_text(text.rstrip("\n") + "\n\n" + block)
    return "appended to"


def resolve_models(tool: Tool, args: argparse.Namespace, existing: dict[str, str],
                   force: bool) -> dict[str, str]:
    """Model per tier. A kept agent file wins; otherwise the flag, the file's current model,
    then the tool's default."""
    defaults = tool.default_models or {}
    models = {}
    for tier in TIERS:
        if tier in existing and not force:
            models[tier] = existing[tier]
        else:
            models[tier] = getattr(args, tier) or existing.get(tier) or defaults.get(tier)
    missing = [tier for tier in TIERS if not models[tier]]
    if missing:
        flags = " ".join(f"--{tier} MODEL" for tier in missing)
        sys.exit(f"{tool.label} has no default models. Pass {flags}.\n"
                 f"To see valid model IDs, {tool.find_models}. "
                 f"Use 'inherit' to keep the main session's model for a tier.")
    return models


def init(args: argparse.Namespace) -> None:
    tool = TOOLS[args.tool]
    project = Path(args.project).resolve()
    if not project.is_dir():
        sys.exit(f"Not a directory: {project}")
    agents_dir = project / tool.agents_dir
    names = {tier: agent_name(tool, tier) for tier in TIERS}
    paths = {tier: agents_dir / f"{names[tier]}{tool.extension}" for tier in TIERS}
    existing = {tier: existing_model(paths[tier]) or "unknown"
                for tier in TIERS if paths[tier].exists()}
    models = resolve_models(tool, args, existing, args.force)

    rules = project / RULES_FILE
    if rules.exists() or (project / LEGACY_RULES_FILE).exists():
        print(f"rules:  kept existing {RULES_FILE if rules.exists() else LEGACY_RULES_FILE}")
    else:
        shutil.copyfile(PLUGIN_ROOT / "defaults" / "model-router.json", rules)
        print(f"rules:  created {RULES_FILE} with default rules")

    agents_dir.mkdir(parents=True, exist_ok=True)
    for tier in TIERS:
        relative = paths[tier].relative_to(project)
        if tier in existing and not args.force:
            ignored = " (--" + tier + " ignored)" if getattr(args, tier) else ""
            print(f"agent:  kept existing {relative} -> {existing[tier]}{ignored}; "
                  "use --force to overwrite")
            continue
        description, body = read_source_agent(tier)
        paths[tier].write_text(
            render_agent(args.tool, names[tier], description, models[tier], body))
        print(f"agent:  wrote {relative} -> {models[tier]}")

    block = render_block(args.tool, tool, names, models)
    action = upsert_block(project / tool.instructions_file, args.tool, block)
    print(f"routing: {action} {tool.instructions_file}")
    print(f"\n{tool.label} is set up. Ask for a non-trivial coding task to see it route.")


def list_tools(_: argparse.Namespace) -> None:
    for key, tool in TOOLS.items():
        defaults = ", ".join(f"{t}={m}" for t, m in (tool.default_models or {}).items())
        print(f"{key:9} {tool.label:11} agents in {tool.agents_dir}/, routing in "
              f"{tool.instructions_file}; default models: {defaults or 'none, pass them'}")
    print("claude    Claude Code  use the plugin in plugins/model-router")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    init_parser = commands.add_parser("init", help="set up model-router for a tool in a project")
    init_parser.add_argument("tool", choices=sorted(TOOLS))
    init_parser.add_argument("--project", default=".", help="project root (default: current dir)")
    for tier in TIERS:
        init_parser.add_argument(f"--{tier}", metavar="MODEL", help=f"model for the {tier} tier")
    init_parser.add_argument("--force", action="store_true", help="overwrite existing agent files")
    init_parser.set_defaults(handler=init)

    commands.add_parser("tools", help="list supported tools").set_defaults(handler=list_tools)

    args = parser.parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
