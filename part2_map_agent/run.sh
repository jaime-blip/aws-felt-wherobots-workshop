#!/bin/bash
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
set -a; source .env 2>/dev/null; set +a
source .venv/bin/activate
python part2_map_agent/agent.py "$@"
