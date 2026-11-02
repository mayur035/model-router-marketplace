# model-router - per-task model routing for AI coding tools

The main agent decides, per task, which tier of model should do the work:

| Tier | Subagent | Claude Code model | Gets |
|---|---|---|---|
| fast | fast-worker | Haiku | renames, boilerplate, simple tests, docs |
| standard | coder | Sonnet | clear-spec features, CRUD, normal refactors |
| deep | deep-reasoner | Opus | concurrency, security, algorithms, design, repeat failures |

Each task is scored on difficulty, ambiguity, and blast radius, or matched against your
project's rules. Failed or escalated tasks move one tier up automatically.

Works in **Claude Code** (plugin, below) and in **Cursor, Codex CLI, Gemini CLI and OpenCode**
(see [Other tools](#other-tools)). All of them share one rules file, `.model-router.json`.

## Install

Requires `bash` and `python3` (standard library only, for `/route-usage`).

```bash
# inside Claude Code
/plugin marketplace add mayur035/model-router-marketplace
/plugin install model-router@model-router-marketplace

# or from a terminal
claude plugin marketplace add mayur035/model-router-marketplace
claude plugin install model-router@model-router-marketplace
```

To install it for everyone on a project, add `--scope project` to the install command and commit
`.claude/settings.json`. Teammates are prompted to install the plugin when they trust the repo.

To work on the plugin itself, clone the repo and add the local folder instead:
`/plugin marketplace add /path/to/model-router-marketplace`.

Restart Claude Code after installing. Recommended main model: `/model opusplan` or `/model opus`.

Check it worked: type `/route` and you should see `route`, `route-explain`, `route-config`
and `route-usage` under `model-router`.

Nothing is written to your project at install time. The first routed task in a project creates
`.model-router.json` with the default rules (see [Choose the model yourself](#choose-the-model-yourself)).
Commit it to share the rules with your team, or add it to `.gitignore` to keep them personal.

## Update

**Installed from GitHub** (`mayur035/model-router-marketplace`):

```bash
claude plugin marketplace update model-router-marketplace
claude plugin update model-router@model-router-marketplace
```

`claude plugin update` only updates the user-scope install. If you also installed the plugin for
a single project, run this from inside that project too (use `--scope local` for a local install):

```bash
claude plugin update model-router@model-router-marketplace --scope project
```

**Installed from a local folder** (`/plugin marketplace add /path/to/model-router-marketplace`):
Claude Code reads the plugin straight from that folder. `claude plugin list` shows it as
"Read from: /path/to/model-router-marketplace/plugins/model-router". Edits apply after
`/reload-plugins` or a restart; no update command is needed.

`claude plugin list` shows each install, its version and where it's read from. Restart Claude
Code afterwards.

If you change the plugin yourself, raise `version` in
`plugins/model-router/.claude-plugin/plugin.json`, then run `claude plugin validate .` and
`claude plugin validate plugins/model-router` to check the manifests.

An update never overwrites an existing rules file. To pick up new default rules in a project,
run `/route-config reset`.

## Use

- `/route add payment retries with idempotency` - plan, route, execute, report
- `/route-explain refactor the auth module` - dry run: show routing only
- `/route-config use opus for reasoning, haiku for tests` - set which tier does which kind of work
- `/route-usage` - tokens used per model in this session, plus proof of which model ran
  (`/route-usage --last` for the most recent routed run only)
- Or just ask normally; the skill activates on non-trivial coding tasks.

## Choose the model yourself

Name a model per task in the request; it wins over the rubric:

```
/route add API tests: claude-haiku-5-5, make checkout idempotent: claude-opus-5-5
```

Or keep standing rules for a project in `.model-router.json` at the project root. A rule names
a `tier` (`fast`, `standard`, `deep`), which every tool maps to its own models, or an exact
`model`, which only works in tools that offer it:

```json
{ "rules": [ { "when": "tests, docs, formatting", "tier": "fast" },
             { "when": "payments, auth, migrations", "tier": "deep" },
             { "when": "migrations", "model": "claude-opus-5-5" } ] }
```

The first routed task in a project creates this file from
`plugins/model-router/defaults/model-router.json` (deep for reasoning and risky work, standard
for clear-spec features, fast for mechanical work), so you can see and edit what's being used.
If several rules fit a task, the stronger tier wins; if none fit, the built-in rubric decides.

Projects set up before 1.6.0 have `.claude/model-router.json` with `model` rules. It still works
everywhere: Claude model names map to tiers by family (haiku = fast, sonnet = standard,
opus = deep). `/route-config reset` moves you to the new file.

You don't have to edit the file by hand:

- `/route-config use opus for reasoning and security, haiku for tests and docs` - add or replace
  rules (Claude names are saved as tiers, so the rules work in every tool)
- `/route-config show` - list the current rules (creates the defaults if missing)
- `/route-config reset` - go back to the plugin defaults
- `/route-config clear` - empty the rules so only the built-in rubric decides

Order of precedence: the request, then the rules file, then the rubric. Short names (`haiku`,
`sonnet`, `opus`, `fable`) and full IDs both work. Claude Code launches subagents by short name,
which runs the current model of that family, so an older full ID runs as the current one; Claude
says so before running. A model named in the request isn't escalated on failure; Claude asks
instead. Models picked by the rules file escalate as usual.

## Proof that routing works

Every time a model-router subagent starts, a hook shows a line like
`model-router: Add GET /orders -> sonnet (chosen) via coder`, so you see the routing as it
happens.

`/route-usage` (or `python3 plugins/model-router/scripts/usage-report.py [--last] [session.jsonl]`) reads
the session transcript in `~/.claude/projects/` and its subagent transcripts. For each subagent it
compares the requested model with the model the API reported on every response. The requested
model is marked `chosen` when a specific model was passed (from the request or a `model` rule),
and `default` when the subagent's own `model:` line applied (including `tier` rules). `OK` means they match; `MISMATCH` means the subagent ran on a different model.
Token counts are summed per model, counting each API response once.

## Test guide

### 1. Quick checks (no Claude session needed)

Run from the repository root:

```bash
# manifests
claude plugin validate .
claude plugin validate plugins/model-router

# routing hook: should print {"systemMessage": "model-router: Add GET /orders -> sonnet (chosen) via coder"}
echo '{"tool_name":"Agent","tool_input":{"subagent_type":"model-router:coder","model":"sonnet","description":"Add GET /orders"}}' \
  | python3 plugins/model-router/scripts/announce-route.py

# rules file: first run prints "created:", second prints "exists:"
D=$(mktemp -d) && bash plugins/model-router/scripts/init-config.sh "$D" \
  && bash plugins/model-router/scripts/init-config.sh "$D" && rm -rf "$D"

# other tools: should list the rules file, three subagents and AGENTS.md
D=$(mktemp -d) && python3 universal/model-router.py init opencode --project "$D" \
  && (cd "$D" && find . -type f | sort) && rm -rf "$D"
```

`claude plugin validate plugins/model-router` warns about a missing icon and a README inside the
plugin folder. That only matters for publishing to the plugin directory.

### 2. Live test in a project

Use a project with tests and git, so you can review or undo the changes. Restart Claude Code
first, so the hooks load, and check that `claude plugin list` shows the version you expect.

**Setup:** start from the default rules.

```
/model-router:route-config reset
```

Expect it to ask for confirmation, then show three rules (deep, standard, fast).

**Test A: rules, all three models, same-file ordering.** Ask for three tasks of different kinds,
two of them in the same file. Replace the bracketed parts with real ones from your project:

```
/model-router:route update README.md to document [feature], add [small endpoint or function] to [file] with tests, and make [money/concurrency/security-sensitive logic] in [same file] safe against [specific failure]
```

| Check | Expected |
|---|---|
| Hook lines | One `model-router: [task] -> [model] (default) via [agent]` line as each subagent starts: README -> haiku, the endpoint -> sonnet, the risky change -> opus |
| Ordering | The two tasks in the same file run one after the other, not at the same time |
| Summary table | The model for each task, with the rule that picked it |
| Usage report | `Scope: last routed run only`, only these three tasks, every row `OK` |

**Test B: a model named in the request beats the rules.** In the same session:

```
/model-router:route add doc comments to every exported function in [file]: claude-sonnet-5-5
```

Expect `-> sonnet (chosen)` even though the docs rule says Haiku, and a usage report listing
only this one task.

**Test C: whole-session report.**

```
/model-router:route-usage
```

Expect `Scope: whole session`, with the tasks from Test A and Test B.

**Test D: rules command.**

```
/model-router:route-config use sonnet for docs and tests
/model-router:route-config show
/model-router:route-config reset
```

Expect a `standard` rule for docs and tests, with added or replaced rules marked, then the
defaults back after `reset`.

Finally, run the project's tests and review `git diff`. The test tasks make real code changes.

### Troubleshooting

| Symptom | Cause and fix |
|---|---|
| No `model-router:` hook lines | Hooks aren't loaded. Restart Claude Code, or run `/reload-plugins` and check `claude plugin list` |
| A row shows `MISMATCH` | The subagent ran on a different model than requested. Check the `model:` line in `agents/*.md` and the model name in your request or rules |
| Rules file "created" again | It was deleted, or this is a new project. Expected |
| Prettier flags the rules file | The file came from a version before 1.5.0. Run `/model-router:route-config reset` and confirm, or `npx prettier --write` on it |
| A `model` rule is skipped in Claude Code | It names a non-Claude model meant for another tool. Use a `tier` rule to cover every tool |
| Usage report lists earlier tasks | Run it with `--last`, or start a new session |
| `--last` shows `no /route run found` | The session never ran `/route` or the routing skill, so the whole session is shown |

## Other tools

`universal/model-router.py` sets up the same routing in Cursor, Codex CLI, Gemini CLI and
OpenCode. It needs only `python3`. For each tool, it writes into your project:

| Tool | Subagents (one per tier) | Routing instructions |
|---|---|---|
| Cursor | `.cursor/agents/*.md` | `AGENTS.md` |
| Codex CLI | `.codex/agents/*.toml` | `AGENTS.md` |
| Gemini CLI | `.gemini/agents/*.md` | `GEMINI.md` |
| OpenCode | `.opencode/agents/*.md` | `AGENTS.md` |

It also creates `.model-router.json` with the default rules if the project has none. The
routing instructions go in a marked section per tool, so several tools can share `AGENTS.md`
and your own text in that file is kept.

```bash
# get the script (once)
git clone https://github.com/mayur035/model-router-marketplace.git ~/model-router-marketplace

python3 ~/model-router-marketplace/universal/model-router.py tools

# OpenCode has defaults (Anthropic models)
python3 ~/model-router-marketplace/universal/model-router.py init opencode

# the others need the model ID for each tier, in that tool's own naming
python3 ~/model-router-marketplace/universal/model-router.py init cursor \
  --fast <model> --standard <model> --deep <model>
```

Run it from the project root, or pass `--project DIR`. Use `inherit` as a model to keep the main
session's model for a tier. Re-running keeps existing subagent files and only refreshes the
routing section; `--force` rewrites them, keeping each tier's current model unless you pass a new
one. To find valid model IDs: `cursor-agent models` for Cursor, `opencode models` for OpenCode,
and the model picker in Codex and Gemini CLI.

What carries over and what doesn't:

| Feature | Claude Code | Other tools |
|---|---|---|
| Rules file, rubric, escalation, same-file ordering | Yes | Yes, via the routing instructions |
| Per-task model named in the request | Any Claude model | Only models one of the three subagents runs |
| Live hook line when a subagent starts | Yes | No; the main agent prints `Routing ...` lines instead |
| `/route-usage` token report and proof of the model | Yes | No; the summary shows the configured model, not a verified one |

Status: generated against each tool's documentation, and the generated files are checked to
parse. Only Claude Code has been tested end to end. Cursor has known reports of subagents not
always using the configured model.

## Customize

- Change the rubric: `plugins/model-router/skills/model-routing/SKILL.md` (Claude Code) and
  `universal/ROUTING.md` (other tools)
- Change which model a tier uses: the `model:` line in `plugins/model-router/agents/*.md` for
  Claude Code; rerun `universal/model-router.py init <tool> --force --<tier> <model>` for others
- Change the subagents' instructions: `plugins/model-router/agents/*.md`. The universal script
  copies them, so rerun it with `--force` afterwards.

## Limits

- The main session's model doesn't switch; work is delegated to subagents on other models.
- Routing relies on the main agent following the instructions, so it's reliable but not a hard
  guarantee. Claude Code adds a hook and a usage report to check it; the other tools don't.

## License

MIT. See [LICENSE](LICENSE).
