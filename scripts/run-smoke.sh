#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -x node_modules/.bin/promptfoo ]]; then
  echo 'Install the pinned Promptfoo dependency with npm ci first.' >&2
  exit 2
fi

export PROMPTFOO_CONFIG_DIR="$repo_root/artifacts/promptfoo-state"
export PROMPTFOO_CACHE_PATH="$repo_root/artifacts/promptfoo-cache"
export PROMPTFOO_LOG_DIR="$repo_root/artifacts/promptfoo-logs"
export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_REMOTE_GENERATION=true
export PROMPTFOO_SAFE_MODE=true

mkdir -p artifacts
node_modules/.bin/promptfoo eval \
  -c promptfooconfig.cjs \
  --no-cache --no-share --max-concurrency 1 \
  --output artifacts/promptfoo-smoke.json artifacts/promptfoo-smoke.html
