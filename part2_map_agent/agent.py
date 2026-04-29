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

# Resolve Felt source id at startup by name (default: "workshop-db").
# Fails fast with a clear message if the source hasn't been connected in Felt.
sys.path.insert(0, str(SKILLS_DIR / "felt-mapping" / "scripts"))
from felt_helpers import resolve_source_id  # noqa: E402

try:
    SOURCE_ID = resolve_source_id()
    _SOURCE_NAME = os.environ.get("FELT_SOURCE_NAME", "workshop-db")
    print(f"✅ Felt source {_SOURCE_NAME!r} → {SOURCE_ID}")
except Exception as e:
    print(f"❌ {e}", file=sys.stderr)
    sys.exit(1)

# ── Skills Plugin ──────────────────────────────────────────────
skills_plugin = AgentSkills(skills=str(SKILLS_DIR))

# ── Seed python_repl state ─────────────────────────────────────
_SEED_CODE = f"""
import os, json, time, psycopg2
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path("{Path(__file__).parent.parent / '.env'}"), override=True)

import felt_python
from felt_python import create_map, add_source_layer, list_layers, update_layer_style, list_library_layers, duplicate_layers

import sys
sys.path.insert(0, "{SKILLS_DIR / 'felt-mapping' / 'scripts'}")
from felt_helpers import wait_for_layer, categorical_style, numeric_style, create_map_with_sql, rename_layer, screenshot_map, find_library_layers, add_library_layer

TOKEN = os.environ.get("FELT_API_TOKEN", "")
SOURCE_ID = "{SOURCE_ID}"  # resolved at startup from FELT_SOURCE_NAME
AURORA_DSN = os.environ.get("AURORA_DSN", "")
print("✅ Ready: psycopg2, felt_python, helpers, TOKEN, SOURCE_ID, AURORA_DSN")
"""

# ── System Prompt ──────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a geospatial map builder agent. You create interactive Felt maps from PostgreSQL/PostGIS data.

## Available Data (workshop schema — 1,035,306 San Diego buildings each)

### workshop.insurance_exposure
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, risk_tier, exposure_delta, triage_priority, relative_risk_band, score_explanation, weather_window_start, weather_window_end

### workshop.cre_risk
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, risk_tier, acquisition_screen_flag (boolean), exposure_magnitude_index, hazard_proximity_m, score_explanation

### workshop.capital_markets_signals
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, disruption_signal, supply_chain_vulnerability, event_density_signal, score_explanation, weather_window_start, weather_window_end

### workshop.energy_asset_risk
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, risk_tier, outage_probability, wildfire_ignition_risk, weather_impact_frequency, score_explanation

### workshop.flood_extent (raster-derived water polygons)
Columns: id, geometry (Polygon, any type), water_class (1/2/3), water_class_name ('open_water'/'partial_surface_water'/'ice_snow_inundation'), observation_date, area_m2, source
Source: OPERA DSWx-S1 Sentinel-1 SAR, clipped to San Diego, ocean polygons removed. Use for flood-proximity queries (`ST_Intersects`, `ST_DWithin`) against building tables.

Risk tiers: low, moderate, elevated, high, critical
Region: San Diego County, CA (bbox: -117.6 to -116.0, 32.5 to 33.5)
Note: `capital_markets_signals` has no `risk_tier` column — use `risk_score` thresholds instead.

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
- `find_library_layers(query, source='all')` — search Org/Felt library by name substring
- `add_library_layer(map_id, name=..., source='all')` — duplicate a library layer onto a map
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

## Library Layers (from Org / Felt Library)

Rasters and reference vectors already in the user's Felt library (e.g. "BP CONUS Burn Probability", basemaps, boundaries) CANNOT be added with `add_source_layer` — that endpoint is only for SQL/data sources and will 422. Use `add_library_layer` instead, which wraps `felt_python.duplicate_layers`:

```python
# By name (substring, case-insensitive) — errors if ambiguous:
layer = add_library_layer(map_id, name="BP CONUS")

# If ambiguous, disambiguate first:
matches = find_library_layers("burn probability")
for m in matches: print(m["id"], m["name"])
layer = add_library_layer(map_id, layer_id="kpn54ZyZRcucq87vmGi6mC")
```

`source` can be `'workspace'` (Org library), `'felt'` (Felt's public library), or `'all'` (default).

## Critical Rules
- ALWAYS use `workshop.` schema prefix in SQL queries — bare table names FAIL
- ALWAYS add LIMIT to queries (max 10000) — 1M rows will timeout
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
            "us.anthropic.claude-opus-4-7",
        ),
        region_name=os.environ.get("AWS_REGION", "us-east-1"),
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
