#!/bin/bash
# Create the project's model-router rules file from the plugin defaults, unless one already exists.
set -euo pipefail

project_dir="${1:-${CLAUDE_PROJECT_DIR:-$PWD}}"
config="$project_dir/.model-router.json"
legacy="$project_dir/.claude/model-router.json"

if [ -f "$config" ]; then
  echo "exists: $config"
  exit 0
fi
if [ -f "$legacy" ]; then
  echo "exists: $legacy"
  exit 0
fi

cp "$(dirname "$0")/../defaults/model-router.json" "$config"
echo "created: $config"
