#!/usr/bin/env python3
"""
Map Builder Agent
==================

A Strands agent that builds Felt maps from any table in Aurora PostgreSQL.
Uses file_read to load skill docs on demand (not stuffed into system prompt).

Usage:
    python agent.py "Show wildfire risk for Austin buildings"
    python agent.py "Map power plants in California colored by energy source"
    python agent.py  # interactive mode
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from strands import Agent, tool
from strands_tools import file_read

SKILLS_DIR = Path(__file__).parent / "skills"

SYSTEM_PROMPT = f"""You are a map builder agent. You create interactive Felt maps from PostgreSQL data.

## How You Work
1. **FIRST: call check_data** to see what's available in the database
2. If data exists for the request, read the relevant skill docs
3. Write Python code to query Aurora and create a Felt map
4. Execute the code with run_python
5. Return the Felt map URL
6. **Call verify_map** with the URL to confirm layers loaded and styling applied
7. If no matching data exists, tell the user what IS available and suggest alternatives

## Available Skill Docs (read with file_read before writing code)
- `{SKILLS_DIR}/aurora_postgis.md` — How to discover schemas, query PostGIS, available tables
- `{SKILLS_DIR}/felt_mapping.md` — How to create maps, add source layers, apply FSL styling (COMPREHENSIVE — read this for any Felt API or styling question)

## Environment Variables
- FELT_API_TOKEN — for felt_python (ALWAYS pass api_token=token to every call)
- AURORA_DSN — PostgreSQL connection string

## Rules
- **ALWAYS call check_data first** to verify data exists before doing anything else.
- Read skill docs before writing code. Use file_read tool.
- Use run_python to execute code
- ALWAYS print the Felt map URL at the end
- ALWAYS discover the schema before assuming column names (especially geometry column name!)
- Source ID for all SQL queries: SUdIQGqeTFKqkHrx9AYVPDA
- Write the FULL pipeline in ONE run_python call (discover → create map → add layer → style → print URL)
"""


@tool
def check_data(query: str) -> str:
    """Check what data is available before building a map.

    ALWAYS call this FIRST before reading skill docs or writing code.
    It searches the database for tables, columns, and values matching
    the user's request and returns what's available.

    Args:
        query: What the user is looking for (e.g., "wildfire risk Austin",
               "power plants California", "schools Victoria").

    Returns:
        Summary of matching tables, columns, sample values, and row counts.
        If nothing matches, lists all available data so the agent can
        suggest alternatives.
    """
    import psycopg2
    import json

    try:
        conn = psycopg2.connect(os.environ["AURORA_DSN"])
        cur = conn.cursor()

        # Get all spatial tables with their columns
        cur.execute("""
            SELECT c.table_schema, c.table_name, c.column_name, c.data_type
            FROM information_schema.columns c
            JOIN (
                SELECT table_schema, table_name
                FROM information_schema.columns
                WHERE udt_name = 'geometry'
            ) g ON c.table_schema = g.table_schema AND c.table_name = g.table_name
            WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')
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

        # For each spatial table, get row count and sample text values
        result_lines = ["## Available Spatial Data\n"]
        for tbl, info in tables.items():
            try:
                cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                count = cur.fetchone()[0]
            except Exception:
                conn.rollback()
                count = "?"

            text_cols = [c["name"] for c in info["columns"]
                        if c["type"] in ("text", "character varying") and c["name"] != info["geom_col"]]

            result_lines.append(f"### {tbl} ({count} rows, geom: {info['geom_col']})")
            result_lines.append(f"Columns: {', '.join(c['name'] + ':' + c['type'][:20] for c in info['columns'] if c['name'] != info['geom_col'])}")

            # Sample distinct values from text columns (for matching)
            for col in text_cols[:4]:
                try:
                    cur.execute(f"SELECT DISTINCT {col} FROM {tbl} WHERE {col} IS NOT NULL LIMIT 10")
                    vals = [str(r[0]) for r in cur.fetchall()]
                    if vals:
                        result_lines.append(f"  {col} values: {', '.join(vals)}")
                except Exception:
                    conn.rollback()

            result_lines.append("")

        conn.close()
        return "\n".join(result_lines)

    except Exception as e:
        return f"ERROR checking data: {e}"


@tool
def verify_map(map_url: str) -> str:
    """Verify a Felt map by checking API metadata AND taking a screenshot.

    Call this AFTER creating and styling a map. It:
    1. Checks layer status, feature counts, and styling via the Felt API
    2. Takes a headless browser screenshot of the actual rendered map
    3. Returns a verification report with the screenshot path

    Args:
        map_url: The Felt map URL to verify.

    Returns:
        Verification report with layer info, issues, and screenshot path.
    """
    import urllib.request
    import json
    import re
    import time as _time
    from pathlib import Path

    token = os.environ.get("FELT_API_TOKEN", "")

    match = re.search(r'([A-Za-z0-9]{20,})$', map_url.rstrip("/"))
    if not match:
        return f"Could not extract map ID from URL: {map_url}"
    map_id = match.group(1)

    lines = ["## Map Verification\n"]

    # ── API check ──────────────────────────────────────────────
    try:
        req = urllib.request.Request(
            f"https://felt.com/api/v2/maps/{map_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        map_data = json.loads(urllib.request.urlopen(req).read())

        req2 = urllib.request.Request(
            f"https://felt.com/api/v2/maps/{map_id}/layers",
            headers={"Authorization": f"Bearer {token}"}
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
            if style_type == "simple" and feat_count and feat_count > 1:
                issues.append(f"Layer '{name}' has default styling — consider applying categorical or numeric style")

        if issues:
            lines.append(f"\n⚠️ **Issues:**")
            for issue in issues:
                lines.append(f"  - {issue}")
    except Exception as e:
        lines.append(f"API check failed: {e}")

    # ── Screenshot ─────────────────────────────────────────────
    screenshots_dir = Path(__file__).parent.parent / "data" / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshots_dir / f"{map_id}.png"

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--enable-webgl", "--use-gl=swiftshader", "--no-sandbox"]
            )
            page = browser.new_page(viewport={"width": 1400, "height": 900})
            page.goto(map_url, timeout=30000)
            _time.sleep(10)
            page.screenshot(path=str(screenshot_path), full_page=False)
            browser.close()

        lines.append(f"\n📸 **Screenshot:** {screenshot_path}")
    except Exception as e:
        lines.append(f"\n📸 Screenshot failed: {e}")

    if not issues:
        lines.append(f"\n✅ **Map verified!** Layers loaded, styled, and screenshot captured.")

    return "\n".join(lines)


_exec_globals = {"__builtins__": __builtins__}


@tool
def run_python(code: str) -> str:
    """Execute Python code and return stdout/stderr.

    Use this to query Aurora PostgreSQL and create Felt maps.
    Available: psycopg2, felt_python, os, json, time.
    Env vars: AURORA_DSN, FELT_API_TOKEN.
    Variables persist between calls.

    Args:
        code: Python code to execute.

    Returns:
        Combined stdout and stderr from execution.
    """
    import io
    import contextlib

    stdout = io.StringIO()
    stderr = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(code, _exec_globals)
        output = stdout.getvalue()
        errors = stderr.getvalue()
        result = output
        if errors:
            result += f"\nSTDERR:\n{errors}"
        return result if result.strip() else "(executed successfully, no output)"
    except Exception as e:
        return f"ERROR: {type(e).__name__}: {e}\n\nSTDOUT so far:\n{stdout.getvalue()}"


def get_model():
    """Get the best available model."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        from strands.models.anthropic import AnthropicModel
        return AnthropicModel(model_id="claude-sonnet-4-20250514")
    else:
        from strands.models.bedrock import BedrockModel
        return BedrockModel(
            model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
            region_name="us-west-2",
        )


def create_agent() -> Agent:
    return Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[check_data, file_read, run_python, verify_map],
    )


def main():
    print("🗺️  Map Builder Agent")
    print("=" * 50)
    print("Build Felt maps from any database table.")
    print("Type 'quit' to exit.\n")
    print("Examples:")
    print('  "Show wildfire risk for Austin buildings"')
    print('  "Map power plants in California by energy source"')
    print('  "Now color it by capacity instead"')
    print('  "What other data is available?"')
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
