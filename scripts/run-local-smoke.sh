#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -x node_modules/.bin/promptfoo ]]; then
  echo 'Install the pinned Promptfoo dependency with npm ci first.' >&2
  exit 2
fi
if [[ "$(node -p 'require("./tasks/smoke.json").length')" != '2' ]]; then
  echo 'Expected exactly two pinned smoke cases.' >&2
  exit 2
fi

# The local provider does not need hosted credentials or endpoint overrides.
unset OPENROUTER_API_KEY OPENAI_API_KEY OPENAI_API_BASE_URL OPENAI_BASE_URL OPENAI_API_HOST
node scripts/preflight-local.cjs

export PROMPTFOO_CONFIG_DIR="$repo_root/artifacts/promptfoo-state"
export PROMPTFOO_CACHE_PATH="$repo_root/artifacts/promptfoo-cache"
export PROMPTFOO_LOG_DIR="$repo_root/artifacts/promptfoo-logs"
export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_REMOTE_GENERATION=true
export PROMPTFOO_SAFE_MODE=true

mkdir -p artifacts
node_modules/.bin/promptfoo eval \
  -c promptfooconfig.local.cjs \
  --no-cache --no-share --max-concurrency 1 --repeat 1 \
  --output artifacts/promptfoo-local-smoke.json artifacts/promptfoo-local-smoke.html
