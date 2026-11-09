---
description: Set which tier or model handles which kind of work in this project (writes .model-router.json)
argument-hint: <e.g. "use opus for reasoning and security, haiku for tests and docs"> | show | reset | clear
---
Manage the model-router rules file in the current project: the rules file the init script prints.
Cursor, Codex, Gemini CLI and OpenCode read the same file. Its format:

```json
{ "rules": [ { "when": "reasoning, security", "tier": "deep" },
             { "when": "migrations", "model": "claude-opus-5-5" } ],
  "auto": true }
```

Tiers are `fast`, `standard` and `deep`; each tool maps them to its own models (here: haiku,
sonnet, opus). `auto` turns the per-prompt routing reminder on or off; `MODEL_ROUTER_AUTO=0`
overrides it.

Request: $ARGUMENTS

First, run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/init-config.sh"` (if `${CLAUDE_PLUGIN_ROOT}` did
not expand, use the init script path in the model-router session-start message). It prints the
rules file it found, or creates `.model-router.json` from the plugin defaults; work on that file.
Say so if it printed `created:`.

For the verbs below, run `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/rules_file.py" <verb>` (if
`${CLAUDE_PLUGIN_ROOT}` did not expand, `rules_file.py` sits next to the init script from the
model-router session-start message).

- **Empty or `show`:** run `rules_file.py show` and print its output as is. Change nothing else.
- **`reset`:** after the user confirms, run `rules_file.py reset`. Print its `reset:` line; if it
  adds `(moved from .claude/model-router.json)`, tell the user the defaults moved to the new file.
- **`clear`:** after the user confirms, run `rules_file.py clear`. It empties `rules` so only the
  built-in rubric decides, and keeps `about` and `auto`.
- **Otherwise:** turn the request into rules.
  1. Split it into (kind of work -> model) pairs. Keep each `when` short: comma-separated
     kinds of work, in the user's words.
  2. Write Claude model names as tiers so the rule works in every tool: haiku -> `fast`,
     sonnet -> `standard`, opus -> `deep`. Write a `model` (exact ID) only when the user names
     a model that isn't one of those three, or says to pin that exact model; if it's a Claude
     model, use the current full ID from your environment. If a name matches no family
     (haiku, sonnet, opus, fable) and isn't clearly another provider's model ID, ask.
  3. If the file exists, merge: a new rule replaces an existing one about the same kind of work;
     keep the rest. If the request says "only" or "replace", start from an empty list.
  4. Write the file as valid JSON with 2-space indentation and each rule as its own
     multi-line object (the layout Prettier produces), ending with a newline. Keep the `about`
     and `auto` keys.
  5. Show the final rules as a table (When | Tier or model), and mark which ones were added or
     replaced.
  6. Run `rules_file.py check`. Fix any `error:` line and check again. Tell the user about any
     `warning:` lines.

Rules apply from the next routed task. A model named in a request still wins over this file.
