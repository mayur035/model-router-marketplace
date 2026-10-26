---
description: Break a task into parts and dynamically route each to Haiku, Sonnet, or Opus
argument-hint: <what to build or fix>
---
Use the model-routing skill for this request. Decompose it, score each task,
announce each routing decision with its reason, delegate to the fast-worker,
coder, and deep-reasoner subagents, escalate on failure, and finish with the summary table.
Apply any models the user chose for specific tasks in the request, or the rules in
`.model-router.json` (or `.claude/model-router.json` in older projects), before the rubric.

Request: $ARGUMENTS
