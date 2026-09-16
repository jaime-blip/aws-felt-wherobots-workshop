#!/usr/bin/env bash
# Launch Kiro on this repo with the workshop credentials exported.
#
# Kiro substitutes ${WHEROBOTS_API_KEY}, ${FELT_API_TOKEN} and ${AURORA_DSN} in
# .kiro/settings/mcp.json from the environment Kiro was started with. It does
# not read .env. Starting Kiro from the Dock, or from a shell without these
# exported, gives MCP servers with unresolved placeholders (postgres fails with
# "Invalid URL: ${AURORA_DSN}", Wherobots calls fail with "Invalid API key").
#
# Usage:  scripts/kiro.sh            # export .env and open Kiro on the repo
#         scripts/kiro.sh --check    # show which variables .env provides, don't launch
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -f .env ]; then
  echo "No .env found. Copy .env.example to .env and fill it in first." >&2
  exit 1
fi
set -a
# shellcheck disable=SC1091
. ./.env
set +a
if [ "${1:-}" = "--check" ]; then
  for v in WHEROBOTS_API_KEY FELT_API_TOKEN AURORA_DSN FELT_SOURCE_NAME; do
    val="${!v:-}"
    case "$val" in
      ""|your-*|*"<"*) echo "  $v: NOT SET (placeholder)";;
      *)               echo "  $v: set";;
    esac
  done
  exit 0
fi
command -v kiro >/dev/null || { echo "kiro not on PATH. Install from https://kiro.dev and enable the shell command." >&2; exit 1; }
exec kiro .
