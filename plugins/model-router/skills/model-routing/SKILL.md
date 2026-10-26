---
name: model-routing
description: Use whenever the user asks to build, implement, fix, or refactor non-trivial code, or mentions model routing, choosing models, Opus/Sonnet/Haiku, or saving cost. Not for planning, writing, client messages, or answering questions. Breaks work into tasks and dynamically routes each one to the right model via the fast-worker (Haiku), coder (Sonnet), and deep-reasoner (Opus) subagents.
---

# Dynamic model routing

You are the orchestrator. Do not write most of the code yourself - plan, score, route, verify.

## 1. Decompose
Break the request into small, independently verifiable tasks. If the work is large,
write the task list to `PLAN.md` so it survives context compaction.

## 2. Score each task
Score each task on three axes (1-3):

| Axis | 1 | 2 | 3 |
|---|---|---|---|
| Reasoning difficulty | mechanical | standard logic | subtle / novel / risky |
| Ambiguity | fully specified | minor gaps | unclear requirements |
| Blast radius | cosmetic | one feature | money, security, data integrity, concurrency |

## 3. Route
- **Any axis = 3** -> `deep-reasoner` (Opus)
- **All axes = 1** -> `fast-worker` (Haiku)
- **Otherwise** -> `coder` (Sonnet)

Context override: if a task needs many large files in view at once (big cross-file refactor),
note it and prefer the model/config with the largest available context window.

## 4. Announce before delegating
Before the first Agent call, print one line per task, as visible text, not only in thinking:

`Routing [task] -> [Haiku|Sonnet|Opus] because [specific reason]`

If the init script printed `created:`, print this line first:
`Created .model-router.json with default rules. Edit it or run /model-router:route-config.`

A model-router hook also shows the user each launch (`model-router: [task] -> [model] via
[agent]`), so the user sees the routing even if these lines are missed.

Run tasks in parallel only when they edit different files. If two tasks will touch the same
file, run them one after the other, so neither overwrites the other's changes.

## 5. Escalate on failure
- If a subagent replies `ESCALATE:` or tests fail after its attempt, re-route that task **one tier up**
  (Haiku -> Sonnet -> Opus) and announce: `Escalating [task] -> [model]: [reason]`.
- If Opus fails, stop and ask the user, summarizing what was tried.

## 6. Verify and report
Only if you delegated at least one task: run the test suite if available, then give a
short markdown table:

| Task | Model | Escalated? | Result |
|---|---|---|---|

Skip the table for planning, writing, or questions, and don't list work you did yourself.

After the table, run the usage report with `--last` (path in the model-router session-start
message), so it covers only this run and not earlier requests in the same session.

Final-message checklist, required whenever you delegated:
- [ ] The `Routing ...` lines were printed before delegating. If you missed them, list them now
      under **Routing**.
- [ ] If the rules file was created this session, say so in one line.
- [ ] Paste the usage report's two tables exactly as the script printed them: same columns,
      same `(chosen)`/`(default)` labels, same numbers. Don't drop columns or reformat.
- [ ] Name any MISMATCH row, or say there were none.

## User-chosen models
The user can pick the model for a task. Precedence: what they say in the request, then the
project rules file, then the rubric in step 3.

- **In the request**, e.g. `add tests: claude-haiku-5-5, fix the race in checkout: claude-opus-5-5`
  or "use opus for X". Short names (`haiku`, `sonnet`, `opus`, `fable`) and full IDs both work.
- **Rules file** `.model-router.json` in the project root (older projects:
  `.claude/model-router.json`). Other tools such as Cursor, Codex, Gemini CLI and OpenCode read
  the same file. Before step 3, run the init script (path in the model-router session-start
  message) from the project root: it creates the file from the plugin defaults if neither
  exists, and prints the path it found or created. If it printed `created:`, tell the user in
  one line that default rules were added there and can be edited or changed with
  `/model-router:route-config`. Then read the file and apply a rule when its `when` text fits
  the task. If more than one rule fits, use the stronger tier. A rule names a `tier` or an
  exact `model`:
  ```json
  { "rules": [ { "when": "tests, docs, formatting", "tier": "fast" },
               { "when": "payments, auth, migrations", "model": "claude-opus-5-5" } ] }
  ```
  Tiers map to subagents with their default models: `fast` -> fast-worker (haiku),
  `standard` -> coder (sonnet), `deep` -> deep-reasoner (opus); launch them without a `model`
  parameter. A `model` that isn't a Claude model (e.g. a GPT or Gemini ID meant for another
  tool) can't run here: skip that rule, say so in one line, and fall through to the rubric.

To run a chosen model, pass its short name as the Agent tool's `model` parameter, and use the
subagent for that tier so the instructions fit: haiku -> fast-worker, sonnet -> coder,
opus or fable -> deep-reasoner. Map a full ID to its short name by the family in it.
The Agent tool only takes short names, which run the current model of that family: if the user
gave a full ID that isn't a current model ID in your environment, say so before running.
If the name matches no family, ask.

Announce it as `Routing [task] -> [model] because the user chose it` (or `because rule "[when]"`).
Don't escalate a model the user named in the request; on failure, stop and ask the user.
Models picked by the rules file escalate as in step 5.

Other overrides:
- "keep it cheap": prefer the lower tier when a task is between two.
- "no routing" or "do it yourself": skip delegation.
