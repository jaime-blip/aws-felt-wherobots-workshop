#!/bin/bash
cd "$(dirname "$0")/.."
source .venv/bin/activate
python part2_map_agent/agent.py "$@"
