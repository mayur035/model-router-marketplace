#!/bin/bash
# Output is added to Claude's context at session start.
echo "model-router plugin is active. For non-trivial build/fix/refactor code work (not planning, writing, or questions), use the model-routing skill: route each task to fast-worker (Haiku), coder (Sonnet), or deep-reasoner (Opus), announce each decision with a reason, and escalate one tier on failure. Recommended main-session model: opus or opusplan."
echo "model-router usage report (tokens per model, actual model per subagent): python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/usage-report.py\""
echo "model-router rules file init (finds .model-router.json or .claude/model-router.json, creates .model-router.json with defaults if neither exists): bash \"${CLAUDE_PLUGIN_ROOT}/scripts/init-config.sh\""
