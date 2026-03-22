#!/usr/bin/env python3
"""
Map Builder Agent
==================

A Strands agent that builds Felt maps from any table in Aurora PostgreSQL.
Uses skill docs (.md files) + python_repl for everything — no hard-coded tools.

Tools:
  - python_repl: execute Python code with state persistence (strands_tools)
  - file_read: read skill docs on demand (strands_tools)

Usage:
    python agent.py "Map wildfire locations colored by cause"
    python agent.py  # interactive mode
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# Configure python_repl: auto-approve execution, non-interactive, keep state
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")
os.environ.setdefault("PYTHON_REPL_INTERACTIVE", "false")
os.environ.setdefault("PYTHON_REPL_RESET_STATE", "false")

from strands import Agent
from strands_tools import file_read, python_repl

# ── Constants ──────────────────────────────────────────────────
SKILLS_DIR = Path(__file__).parent / "skills"
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "e5UKkPZxTwiR9CxbRzFw9AZA")

# ── Seed python_repl state ─────────────────────────────────────
_SEED_CODE = f"""
import os, json, time, psycopg2
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path("{Path(__file__).parent.parent / '.env'}"), override=True)

import felt_python
from felt_python import create_map, add_source_layer, list_layers, update_layer_style

import sys
sys.path.insert(0, "{Path(__file__).parent / 'skills'}")
from felt_helpers import wait_for_layer, categorical_style, numeric_style, create_map_with_sql

TOKEN = os.environ.get("FELT_API_TOKEN", "")
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "{SOURCE_ID}")
AURORA_DSN = os.environ.get("AURORA_DSN", "")
print("✅ Ready: psycopg2, felt_python, helpers, TOKEN, SOURCE_ID, AURORA_DSN")
"""

# ── System Prompt ──────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a geospatial map builder agent. You create interactive Felt maps from PostgreSQL/PostGIS data.

## Your Tools
- **python_repl** — execute Python code (state persists between calls)
- **file_read** — read skill documentation files

## Skill Docs (read with file_read when you need patterns/examples)
- `{SKILLS_DIR}/aurora_postgis.md` — How to discover tables, columns, sample values, PostGIS queries
- `{SKILLS_DIR}/felt_mapping.md` — How to create maps, add source layers, apply FSL styling

## Workflow
1. Read `aurora_postgis.md` to learn the discovery pattern
2. Use `python_repl` to discover what tables/columns are available
3. Read `felt_mapping.md` for styling patterns (if needed)
4. Use `python_repl` to create the map (create → add layer → wait → style)
5. Use `python_repl` to verify the map (see VERIFICATION section in felt_mapping.md)

## python_repl Environment (pre-loaded, no imports needed)
- `psycopg2`, `os`, `json`, `time` — standard
- `AURORA_DSN` — connection string for psycopg2.connect()
- `create_map`, `add_source_layer`, `list_layers`, `update_layer_style` — from felt_python
- `wait_for_layer(map_id)` — polls until layer processing completes
- `categorical_style(attribute, top_n=10)` — builds valid FSL for categories
- `numeric_style(attribute)` — builds valid FSL for gradients
- `TOKEN`, `SOURCE_ID` — Felt credentials

## Code Patterns

### Discover tables:
```python
conn = psycopg2.connect(AURORA_DSN)
cur = conn.cursor()
cur.execute("SELECT table_name FROM information_schema.columns WHERE udt_name='geometry' AND table_schema='public'")
print([r[0] for r in cur.fetchall()])
conn.close()
```

### Create a styled map:
```python
m = create_map(title="My Map", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]

params = {{"from": "sql", "source_id": SOURCE_ID, "query": "SELECT * FROM public.my_table"}}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)

layer = wait_for_layer(map_id)
update_layer_style(map_id=map_id, layer_id=layer["id"], style=categorical_style("col", top_n=10), api_token=TOKEN)
print(f"✅ {{map_url}}")
```

### Multi-layer:
```python
for table, col in [("public.t1", "c1"), ("public.t2", "c2")]:
    add_source_layer(map_id=map_id, source_layer_params={{"from": "sql", "source_id": SOURCE_ID, "query": f"SELECT * FROM {{table}}"}}, api_token=TOKEN)
    layer = wait_for_layer(map_id)
    update_layer_style(map_id=map_id, layer_id=layer["id"], style=categorical_style(col, top_n=10), api_token=TOKEN)
```

## Rules
- Read the skill doc FIRST if you haven't already — don't guess at patterns
- Write the FULL pipeline in as few python_repl calls as possible
- NEVER create more than ONE map per request
- ALWAYS print the map URL
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
