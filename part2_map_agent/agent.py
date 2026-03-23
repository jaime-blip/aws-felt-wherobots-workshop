#!/usr/bin/env python3
"""
Map Builder Agent
==================

A Strands agent that builds Felt maps from any table in Aurora PostgreSQL.

Architecture:
  - Skills (AgentSkills plugin): aurora-postgis, felt-mapping
  - Tools: python_repl (code execution), file_read (read skill resources)
  - No custom tools — everything is skills + code execution

Usage:
    python agent.py "Map wildfire locations colored by cause"
    python agent.py  # interactive mode
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# Configure python_repl: auto-approve, non-interactive, keep state
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")
os.environ.setdefault("PYTHON_REPL_INTERACTIVE", "false")
os.environ.setdefault("PYTHON_REPL_RESET_STATE", "false")

from strands import Agent, AgentSkills
from strands_tools import file_read, python_repl

# ── Constants ──────────────────────────────────────────────────
SKILLS_DIR = Path(__file__).parent / "skills"
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "rYZY3hxzTJCJnEZP2k1r0B")

# ── Skills Plugin ──────────────────────────────────────────────
skills_plugin = AgentSkills(skills=str(SKILLS_DIR))

# ── Seed python_repl state ─────────────────────────────────────
_SEED_CODE = f"""
import os, json, time, psycopg2
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path("{Path(__file__).parent.parent / '.env'}"), override=True)

import felt_python
from felt_python import create_map, add_source_layer, list_layers, update_layer_style

import sys
sys.path.insert(0, "{SKILLS_DIR / 'felt-mapping' / 'scripts'}")
from felt_helpers import wait_for_layer, categorical_style, numeric_style, create_map_with_sql, rename_layer, screenshot_map

TOKEN = os.environ.get("FELT_API_TOKEN", "")
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "{SOURCE_ID}")
AURORA_DSN = os.environ.get("AURORA_DSN", "")
print("✅ Ready: psycopg2, felt_python, helpers, TOKEN, SOURCE_ID, AURORA_DSN")
"""

# ── System Prompt ──────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a geospatial map builder agent. You create interactive Felt maps from PostgreSQL/PostGIS data.

## Workflow
1. Activate the relevant skill(s) to get instructions
2. Use `python_repl` to discover data and build maps
3. Use `file_read` to read skill resources (scripts, references) when needed

## python_repl Environment (pre-loaded after seeding)
- `psycopg2`, `os`, `json`, `time` — standard
- `AURORA_DSN` — connection string for psycopg2.connect()
- `create_map`, `add_source_layer`, `list_layers`, `update_layer_style` — from felt_python
- `wait_for_layer(map_id)` — polls until layer processing completes
- `categorical_style(attribute, top_n=10)` — builds valid FSL
- `numeric_style(attribute)` — builds valid FSL
- `rename_layer(map_id, layer_id, name)` — rename a layer (default names are ugly)
- `screenshot_map(map_url, wait_s=10)` — take a screenshot with headless Playwright, returns path
- `TOKEN`, `SOURCE_ID` — Felt credentials

## Code Pattern (single layer)
```python
m = create_map(title="My Map", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]

params = {{"from": "sql", "source_id": SOURCE_ID, "query": "SELECT * FROM workshop.insurance_exposure WHERE risk_tier = 'Critical'"}}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)

layer = wait_for_layer(map_id)
update_layer_style(map_id=map_id, layer_id=layer["id"], style=categorical_style("col", top_n=10), api_token=TOKEN)
rename_layer(map_id, layer["id"], "My Layer Name")
screenshot_map(map_url)
print(f"✅ {{map_url}}")
```

## Rules
- Activate skills before writing code — don't guess at API patterns
- Write the FULL pipeline in as few python_repl calls as possible
- NEVER create more than ONE map per request
- ALWAYS print the map URL on its own line with no markdown formatting (no ** or [] around it)
- ALWAYS rename layers with `rename_layer()` — default names are ugly ("Aurora 3 - CustomQuery")
- ALWAYS take a screenshot at the end with `screenshot_map(map_url)` — shows the result
"""


# ── Agent Factory ──────────────────────────────────────────────

def get_model():
    """Get the best available Bedrock model."""
    from strands.models.bedrock import BedrockModel
    return BedrockModel(
        model_id=os.environ.get(
            "BEDROCK_MODEL_ID",
            "us.anthropic.claude-sonnet-4-20250514-v1:0",
        ),
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
    )


def create_agent() -> Agent:
    """Create the map builder agent."""
    agent = Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[python_repl, file_read],
        plugins=[skills_plugin],
    )

    # Seed python_repl with imports and credentials
    agent.tool.python_repl(code=_SEED_CODE)

    return agent


# ── CLI ────────────────────────────────────────────────────────

def main():
    print("🗺️  Map Builder Agent")
    print("=" * 50)
    print("Build Felt maps from any database table.")
    print("Type 'quit' to exit.\n")
    print("Examples:")
    print('  "Map wildfire locations colored by cause"')
    print('  "Show all tables on one map"')
    print('  "What data is available?"')
    print()

    agent = create_agent()

    # Single prompt from CLI args
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"🔍 {prompt}\n")
        agent(prompt)
        print()

    # Interactive loop
    while True:
        try:
            prompt = input("🔍 > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Bye!")
            break
        if not prompt:
            continue
        if prompt.lower() in ("quit", "exit", "q"):
            print("👋 Bye!")
            break
        print()
        agent(prompt)
        print()


if __name__ == "__main__":
    main()
