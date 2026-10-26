---
description: Show tokens used per model in this session, and prove which model answered each subagent
argument-hint: [--last] [path/to/session.jsonl]
---
Run the model-router usage report with Bash and show its output to the user unchanged:

`python3 "${CLAUDE_PLUGIN_ROOT}/scripts/usage-report.py" $ARGUMENTS`

If `${CLAUDE_PLUGIN_ROOT}` did not expand, use the usage report path given in the
model-router session-start message.

`--last` limits it to the most recent routed run; without it, the whole session is covered.

After the tables, add at most two lines: name any row marked MISMATCH, and note that
"Actual" is the model the API reported for each response, read from the session transcript.
