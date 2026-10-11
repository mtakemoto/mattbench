#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -x node_modules/.bin/promptfoo ]]; then
  echo 'Install the pinned Promptfoo dependency with npm ci first.' >&2
  exit 2
fi
env_file_args=()
if [[ -z "${OPENROUTER_API_KEY:-}" ]]; then
  if [[ ! -f .env ]] || ! rg -q '^OPENROUTER_API_KEY=.+$' .env; then
    echo 'Add OPENROUTER_API_KEY to the ignored .env file or export it in this process.' >&2
    exit 2
  fi
  env_file_args=(--env-file .env)
fi
if [[ "${MATTBENCH_CONFIRMED_WEEKLY_CAP_USD:-}" != '20' ]]; then
  echo 'Set MATTBENCH_CONFIRMED_WEEKLY_CAP_USD=20 after verifying the $20/week workspace cap.' >&2
  exit 2
fi
if [[ "$(node -p 'require("./tasks/smoke.json").length')" != '2' ]]; then
  echo 'Expected exactly two pinned smoke cases; refusing a paid run.' >&2
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
  -c promptfooconfig.openrouter.cjs \
  "${env_file_args[@]}" \
  --no-cache --no-share --max-concurrency 1 --repeat 1 \
  --output artifacts/promptfoo-openrouter-glm-5.3-flash-v2.json artifacts/promptfoo-openrouter-glm-5.3-flash-v2.html
