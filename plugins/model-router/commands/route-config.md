---
description: Set which tier or model handles which kind of work in this project (writes .model-router.json)
argument-hint: <e.g. "use opus for reasoning and security, haiku for tests and docs"> | show | reset | clear
---
Manage the model-router rules file in the current project: `.model-router.json` in the project
root, or `.claude/model-router.json` in older projects. Cursor, Codex, Gemini CLI and OpenCode
read the same file. Its format:

```json
{ "rules": [ { "when": "reasoning, security", "tier": "deep" },
             { "when": "migrations", "model": "claude-opus-5-5" } ] }
```

Tiers are `fast`, `standard` and `deep`; each tool maps them to its own models (here: haiku,
sonnet, opus).

Request: $ARGUMENTS

First, run `bash "${CLAUDE_PLUGIN_ROOT}/scripts/init-config.sh"` (if `${CLAUDE_PLUGIN_ROOT}` did
not expand, use the init script path in the model-router session-start message). It prints the
rules file it found, or creates `.model-router.json` from the plugin defaults; work on that file.
Say so if it printed `created:`.

- **Empty or `show`:** print the current rules as a table (When | Tier or model). Change nothing
  else.
- **`reset`:** after the user confirms, replace the file with the plugin defaults
  (delete it, then run the init script). If the old file was `.claude/model-router.json`, the
  defaults go to `.model-router.json`; mention that.
- **`clear`:** after the user confirms, replace `rules` with an empty list so only the built-in
  rubric decides. Keep the file so defaults aren't recreated on the next routed task.
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
     multi-line object (the layout Prettier produces), ending with a newline, and keep the
     `about` key.
  5. Show the final rules as a table (When | Tier or model), and mark which ones were added or
     replaced.

Rules apply from the next routed task. A model named in a request still wins over this file.
