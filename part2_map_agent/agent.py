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

## Available Data (workshop schema — 358,985 San Diego buildings each)

### workshop.insurance_exposure
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score (0-0.7), risk_tier (low/moderate/elevated/high), exposure_delta, triage_priority, estimated_loss_band, score_explanation

### workshop.cre_risk
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score (0-0.7), risk_tier, acquisition_screen_flag (boolean), environmental_risk_index, hazard_proximity_m, score_explanation

### workshop.capmarkets_signals
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, disruption_probability (0-1, sigmoid), supply_chain_vulnerability, event_signal_strength, score_explanation

### workshop.energy_infra_risk
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score (0-0.7), risk_tier, outage_probability, vegetation_encroachment_risk, weather_impact_frequency, score_explanation

Risk tiers: low, moderate, elevated, high (no "critical" tier exists)
Region: San Diego County, CA (bbox: -117.6 to -116.0, 32.5 to 33.5)

## Workflow
1. Activate the felt-mapping skill for styling instructions
2. Use `python_repl` to build maps — write the FULL pipeline in ONE python_repl call
3. DO NOT run discovery queries — use the schema above

## python_repl Environment (pre-loaded)
- `psycopg2`, `os`, `json`, `time`, `AURORA_DSN` — for direct DB queries
- `create_map`, `add_source_layer`, `list_layers`, `update_layer_style` — from felt_python
- `wait_for_layer(map_id)` — polls until layer processing completes
- `categorical_style(attribute, top_n=10)` — builds FSL for text columns
- `numeric_style(attribute)` — builds FSL for numeric columns
- `rename_layer(map_id, layer_id, name)` — rename a layer
- `screenshot_map(map_url, wait_s=10)` — screenshot with headless Playwright
- `TOKEN`, `SOURCE_ID` — Felt credentials

## Code Pattern (single layer)
```python
m = create_map(title="My Map", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]

params = {{"from": "sql", "source_id": SOURCE_ID, "query": "SELECT * FROM workshop.insurance_exposure WHERE risk_tier IN ('elevated','high') LIMIT 5000"}}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)

layer = wait_for_layer(map_id)
update_layer_style(map_id=map_id, layer_id=layer["id"], style=categorical_style("risk_tier", top_n=10), api_token=TOKEN)
rename_layer(map_id, layer["id"], "Insurance Risk")
screenshot_map(map_url)
print(f"✅ {{map_url}}")
```

## Multi-layer Pattern
```python
m = create_map(title="Multi Layer Map", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]

# Layer 1
params1 = {{"from": "sql", "source_id": SOURCE_ID, "query": "SELECT * FROM workshop.insurance_exposure WHERE risk_tier = 'high' LIMIT 5000"}}
add_source_layer(map_id=map_id, source_layer_params=params1, api_token=TOKEN)
layer1 = wait_for_layer(map_id, expect_count=1)
rename_layer(map_id, layer1["id"], "High Risk")

# Layer 2
params2 = {{"from": "sql", "source_id": SOURCE_ID, "query": "SELECT * FROM workshop.cre_risk WHERE risk_tier = 'elevated' LIMIT 5000"}}
add_source_layer(map_id=map_id, source_layer_params=params2, api_token=TOKEN)
layer2 = wait_for_layer(map_id, expect_count=2)
rename_layer(map_id, layer2["id"], "Elevated CRE Risk")

screenshot_map(map_url)
print(f"✅ {{map_url}}")
```

## Critical Rules
- ALWAYS use `workshop.` schema prefix in SQL queries — bare table names FAIL
- ALWAYS add LIMIT to queries (max 10000) — 358K rows will timeout
- Write the FULL pipeline in as few python_repl calls as possible (ideally ONE)
- NEVER run discovery/exploration queries — use the schema above
- NEVER create more than ONE map per request
- ALWAYS rename layers — default names are ugly
- ALWAYS screenshot at the end
- Print map URL on its own line, no markdown formatting
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
