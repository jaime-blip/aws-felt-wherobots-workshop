#!/usr/bin/env python3
"""
Map Builder Agent
==================

A Strands agent that builds Felt maps from any table in Aurora PostgreSQL.

Tools:
  - check_data: discover tables/columns in the database (custom @tool)
  - verify_map: check layers + screenshot a completed map (custom @tool)
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

from strands import Agent, tool
from strands_tools import file_read, python_repl

# ── Constants ──────────────────────────────────────────────────
SKILLS_DIR = Path(__file__).parent / "skills"
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "e5UKkPZxTwiR9CxbRzFw9AZA")
FELT_TOKEN = os.environ.get("FELT_API_TOKEN", "")

# ── Seed python_repl state ─────────────────────────────────────
# The official python_repl has persistent state via dill.
# We seed it on startup so the agent's code has everything ready.
_SEED_CODE = f"""
import os, json, time
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path("{Path(__file__).parent.parent / '.env'}"), override=True)

import felt_python
from felt_python import create_map, add_source_layer, list_layers, update_layer_style

import sys
sys.path.insert(0, "{Path(__file__).parent / 'scripts'}")
from felt_helpers import wait_for_layer, categorical_style, numeric_style, create_map_with_sql

TOKEN = os.environ.get("FELT_API_TOKEN", "")
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "{SOURCE_ID}")
print("✅ Environment seeded: felt_python, helpers, TOKEN, SOURCE_ID ready")
"""

# ── System Prompt ──────────────────────────────────────────────
SYSTEM_PROMPT = f"""You are a geospatial map builder agent. You create interactive Felt maps from PostgreSQL/PostGIS data.

## Workflow
1. **check_data** — ALWAYS call first to discover tables, columns, sample values
2. **file_read** — read skill docs for API details (only when needed)
3. **python_repl** — write and execute Python to create Felt maps
4. **verify_map** — confirm the map loaded correctly (call at the end)

## Skill Docs (read with file_read when you need API details)
- `{SKILLS_DIR}/aurora_postgis.md` — PostGIS query patterns
- `{SKILLS_DIR}/felt_mapping.md` — Felt API, source layers, FSL styling (COMPREHENSIVE)

## python_repl Environment
The following are pre-imported and ready to use (do NOT re-import):
- `create_map(title, api_token=TOKEN)` → dict with "id", "url"
- `add_source_layer(map_id, source_layer_params, api_token=TOKEN)`
- `list_layers(map_id, api_token=TOKEN)` → list of layer dicts
- `update_layer_style(map_id, layer_id, style, api_token=TOKEN)`
- `wait_for_layer(map_id, timeout_s=90)` → polls until completed, returns layer dict
- `categorical_style(attribute, categories=None, colors=None, top_n=10)` → valid FSL dict
- `numeric_style(attribute, palette="@ylRed")` → valid FSL dict
- `create_map_with_sql(title, sql, style=None)` → full pipeline, returns dict
- `TOKEN`, `SOURCE_ID` — credentials already set
- `os`, `json`, `time` — standard library

## Code Pattern (single layer)
```python
m = create_map(title="My Map", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]
print(f"Map: {{map_url}}")

params = {{"from": "sql", "source_id": SOURCE_ID, "query": "SELECT * FROM public.my_table"}}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)

layer = wait_for_layer(map_id)
style = categorical_style("my_column", top_n=10)
update_layer_style(map_id=map_id, layer_id=layer["id"], style=style, api_token=TOKEN)
print(f"✅ {{map_url}}")
```

## Multi-layer pattern
Add layers ONE AT A TIME, style each before adding the next:
```python
for table, col in [("public.t1", "col1"), ("public.t2", "col2")]:
    params = {{"from": "sql", "source_id": SOURCE_ID, "query": f"SELECT * FROM {{table}}"}}
    add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)
    layer = wait_for_layer(map_id)
    update_layer_style(map_id=map_id, layer_id=layer["id"], style=categorical_style(col, top_n=10), api_token=TOKEN)
```

## Rules
- ALWAYS call check_data first
- Write the FULL pipeline in ONE python_repl call (create → add → wait → style → print URL)
- NEVER create more than ONE map per request
- ALWAYS print the map URL at the end
- Source ID: `{SOURCE_ID}`
"""


# ── Custom Tools ───────────────────────────────────────────────

@tool
def check_data(query: str) -> str:
    """Discover spatial tables, columns, and sample values in the database.

    ALWAYS call this FIRST before writing any code. Returns all spatial tables
    with their schemas, row counts, and example values for text columns.

    Args:
        query: What the user is looking for (e.g., "wildfire", "air quality", "buildings").

    Returns:
        Formatted summary of available spatial tables and their contents.
    """
    import psycopg2

    try:
        conn = psycopg2.connect(os.environ["AURORA_DSN"])
        cur = conn.cursor()

        cur.execute("""
            SELECT c.table_schema, c.table_name, c.column_name, c.data_type
            FROM information_schema.columns c
            JOIN (
                SELECT table_schema, table_name
                FROM information_schema.columns
                WHERE udt_name = 'geometry'
            ) g ON c.table_schema = g.table_schema AND c.table_name = g.table_name
            WHERE c.table_schema = 'public'
              AND c.table_name NOT IN ('geometry_columns', 'geography_columns',
                                       'spatial_ref_sys', 'raster_columns', 'raster_overviews')
            ORDER BY c.table_schema, c.table_name, c.ordinal_position
        """)

        tables = {}
        for schema, table, col, dtype in cur.fetchall():
            key = f"{schema}.{table}"
            if key not in tables:
                tables[key] = {"columns": [], "geom_col": None}
            tables[key]["columns"].append({"name": col, "type": dtype})
            if dtype == "USER-DEFINED":
                tables[key]["geom_col"] = col

        lines = [f"## Available Spatial Data (Source ID: {SOURCE_ID})\n"]
        for tbl, info in tables.items():
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                count = cur.fetchone()[0]
            except Exception:
                conn.rollback()
                count = "?"

            display_cols = [c for c in info["columns"]
                           if c["name"] != info["geom_col"]
                           and not c["name"].startswith("felt:")]
            text_cols = [c["name"] for c in display_cols
                        if c["type"] in ("text", "character varying")]

            lines.append(f"### {tbl} ({count} rows, geom: {info['geom_col']})")
            lines.append(f"Columns: {', '.join(c['name'] + ':' + c['type'][:20] for c in display_cols[:15])}")
            if len(display_cols) > 15:
                lines.append(f"  ... and {len(display_cols) - 15} more columns")

            for col in text_cols[:4]:
                try:
                    cur.execute(f'SELECT DISTINCT "{col}" FROM {tbl} WHERE "{col}" IS NOT NULL LIMIT 8')
                    vals = [str(r[0])[:50] for r in cur.fetchall()]
                    if vals:
                        lines.append(f"  {col}: {', '.join(vals)}")
                except Exception:
                    conn.rollback()
            lines.append("")

        conn.close()
        return "\n".join(lines)
    except Exception as e:
        return f"ERROR: {e}"


@tool
def verify_map(map_url: str) -> str:
    """Verify a Felt map has loaded correctly.

    Checks layer status, feature counts, and styling via the Felt API.
    Takes a headless browser screenshot if Playwright is available.
    Call this AFTER creating and styling a map.

    Args:
        map_url: The full Felt map URL to verify.

    Returns:
        Verification report with layer details and any issues found.
    """
    import urllib.request
    import json
    import re
    import time as _time

    token = os.environ.get("FELT_API_TOKEN", "")
    match = re.search(r'([A-Za-z0-9]{20,})$', map_url.rstrip("/"))
    if not match:
        return f"Could not extract map ID from URL: {map_url}"
    map_id = match.group(1)

    lines = ["## Map Verification\n"]

    try:
        req = urllib.request.Request(
            f"https://felt.com/api/v2/maps/{map_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        map_data = json.loads(urllib.request.urlopen(req).read())

        req2 = urllib.request.Request(
            f"https://felt.com/api/v2/maps/{map_id}/layers",
            headers={"Authorization": f"Bearer {token}"},
        )
        layers = json.loads(urllib.request.urlopen(req2).read())

        lines.append(f"**Title:** {map_data.get('title', '?')}")
        lines.append(f"**URL:** {map_data.get('url', '?')}")
        lines.append(f"**Layers:** {len(layers)}\n")

        issues = []
        for layer in layers:
            name = layer.get("name", "Unnamed")
            status = layer.get("status", "?")
            feat_count = layer.get("metadata", {}).get("feature_count")
            style_type = layer.get("style", {}).get("type", "none")
            lines.append(f"- **{name}**: status={status}, features={feat_count or '?'}, style={style_type}")
            if status == "failed":
                issues.append(f"Layer '{name}' failed to process")

        if issues:
            lines.append("\n⚠️ **Issues:**")
            for issue in issues:
                lines.append(f"  - {issue}")

    except Exception as e:
        lines.append(f"API check failed: {e}")
        issues = [str(e)]

    # Screenshot (best-effort)
    screenshots_dir = Path(__file__).parent.parent / "data" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshots_dir / f"{map_id}.png"

    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(map_url, timeout=30000)
            _time.sleep(10)
            page.screenshot(path=str(screenshot_path), full_page=False)
            browser.close()
        lines.append(f"\n📸 Screenshot: {screenshot_path}")
    except Exception as e:
        lines.append(f"\n📸 Screenshot skipped: {e}")

    if not issues:
        lines.append("\n✅ Map verified successfully!")

    return "\n".join(lines)


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
    """Create the map builder agent with all tools."""
    agent = Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[check_data, verify_map, python_repl, file_read],
    )

    # Seed python_repl with our environment (imports, helpers, tokens)
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
    print('  "Show all 6 tables on one map"')
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
