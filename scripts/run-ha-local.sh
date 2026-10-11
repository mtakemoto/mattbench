#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if [[ ! -x node_modules/.bin/promptfoo ]]; then
  echo 'Install the pinned dependencies with npm ci first.' >&2
  exit 2
fi
if [[ "$(node -p 'require("./tasks/ha-readonly.json").length')" != '1' ]]; then
  echo 'Expected exactly one pinned Home Assistant task.' >&2
  exit 2
fi

unset OPENROUTER_API_KEY OPENAI_API_KEY OPENAI_API_BASE_URL OPENAI_BASE_URL OPENAI_API_HOST
node scripts/preflight-local.cjs

export PROMPTFOO_CONFIG_DIR="$repo_root/artifacts/promptfoo-state"
export PROMPTFOO_CACHE_PATH="$repo_root/artifacts/promptfoo-cache"
export PROMPTFOO_LOG_DIR="$repo_root/artifacts/promptfoo-logs"
export PROMPTFOO_DISABLE_TELEMETRY=1
export PROMPTFOO_DISABLE_REMOTE_GENERATION=true
export PROMPTFOO_SAFE_MODE=true
output_basename="${MATTBENCH_HA_OUTPUT_BASENAME:-promptfoo-ha-local}"
if [[ "$output_basename" != 'promptfoo-ha-local' && "$output_basename" != 'promptfoo-ha-offline' ]]; then
  echo 'Unsupported Home Assistant output basename.' >&2
  exit 2
fi
export MATTBENCH_HA_TRACE="$repo_root/artifacts/${output_basename}-tool-calls.jsonl"

mkdir -p artifacts
: > "$MATTBENCH_HA_TRACE"
node_modules/.bin/promptfoo eval \
  -c promptfooconfig.ha-local.cjs \
  --no-cache --no-share --max-concurrency 1 --repeat 1 \
  --output "artifacts/${output_basename}.json" "artifacts/${output_basename}.html"
