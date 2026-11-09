"""The tier catalog: which tier agent serves each tier, read from the plugin's agent files."""

import re
from dataclasses import dataclass
from pathlib import Path

_DEFAULT_AGENTS_DIR = Path(__file__).resolve().parent.parent / "agents"
_TIER_AGENTS = {"fast": "fast-worker", "standard": "coder", "deep": "deep-reasoner"}
_PREFIX = "model-router:"


class TierCatalogError(Exception):
    pass


@dataclass(frozen=True)
class Tier:
    tier: str
    agent: str
    model: str
    description: str
    body: str


def _parse(text: str) -> tuple[dict[str, str], str] | None:
    match = re.match(r"---\n(.*?)\n---\n(.*)", text.replace("\r\n", "\n"), re.S)
    if not match:
        return None
    fields = dict(re.findall(r"^(\w+):[ \t]*(.*?)[ \t]*$", match.group(1), re.M))
    return fields, match.group(2).strip() + "\n"


def tiers(agents_dir: Path | None = None) -> dict[str, Tier]:
    agents_dir = Path(agents_dir) if agents_dir else _DEFAULT_AGENTS_DIR
    parsed = {}
    for path in sorted(agents_dir.glob("*.md")):
        result = _parse(path.read_text(encoding="utf-8"))
        if result and result[0].get("name"):
            parsed[result[0]["name"]] = result
    catalog = {}
    for tier, agent in _TIER_AGENTS.items():
        fields, body = parsed.get(agent, ({}, ""))
        if not fields.get("model"):
            raise TierCatalogError(f"tier {tier!r}: agent {agent!r} has no model in {agents_dir}")
        catalog[tier] = Tier(tier, agent, fields.get("model", ""),
                             fields.get("description", ""), body)
    return catalog


def for_agent(name: str, agents_dir: Path | None = None) -> Tier | None:
    name = name.removeprefix(_PREFIX)
    return next((t for t in tiers(agents_dir).values() if t.agent == name), None)
