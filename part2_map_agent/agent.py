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
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "e5UKkPZxTwiR9CxbRzFw9AZA")
TOKEN = os.environ.get("FELT_API_TOKEN", "")

SYSTEM_PROMPT = f"""You are a map builder agent. You create interactive Felt maps from PostgreSQL data via Felt's source layer API.

## How You Work
1. **FIRST: call check_data** to see what tables/datasets are available
2. If data exists for the request, read the relevant skill docs
3. Write Python code to create a Felt map using add_source_layer with SQL
4. Execute the code with run_python
5. Return the Felt map URL
6. **Call verify_map** with the URL to confirm layers loaded and styling applied
7. If no matching data exists, tell the user what IS available and suggest alternatives

## Available Skill Docs (read with file_read before writing code)
- `{SKILLS_DIR}/aurora_postgis.md` — How to discover schemas, query PostGIS, available tables
- `{SKILLS_DIR}/felt_mapping.md` — How to create maps, add source layers, apply FSL styling (COMPREHENSIVE — read this for any Felt API or styling question)

## Environment Variables (already configured)
- FELT_API_TOKEN — for felt_python (ALWAYS pass api_token=token to every call)
- FELT_SOURCE_ID — the Felt source connected to Aurora PostgreSQL

## Rules
- **ALWAYS call check_data first** to verify data exists before doing anything else.
- Read skill docs before writing code. Use file_read tool.
- Use run_python to execute code
- ALWAYS print the Felt map URL at the end
- **Discover columns via SQL**: use run_python with add_source_layer to run `SELECT * FROM table LIMIT 0` or similar to discover column names — DON'T assume column names!
- Source ID for all SQL queries: `{SOURCE_ID}`
- Write the FULL pipeline in ONE run_python call (create map → add layer → poll for completion → style → print URL)
- **Import helpers**: `sys.path.insert(0, '{Path(__file__).parent / "scripts"}'); from felt_helpers import wait_for_layer, categorical_style, numeric_style`
"""


@tool
def check_data(query: str) -> str:
    """Check what data is available before building a map.

    ALWAYS call this FIRST before reading skill docs or writing code.
    Lists all datasets (tables) available in the connected Felt source,
    including geometry types. Use this to find the right table for the
    user's request.

    Args:
        query: What the user is looking for (e.g., "wildfire risk",
               "power plants California", "air quality").

    Returns:
        Summary of available datasets with geometry types.
        Use run_python with a discovery SQL query to get column details
        for a specific table.
    """
    import urllib.request
    import json

    try:
        req = urllib.request.Request(
            f"https://felt.com/api/v2/sources/{SOURCE_ID}",
            headers={"Authorization": f"Bearer {TOKEN}"}
        )
        source = json.loads(urllib.request.urlopen(req).read())
        datasets = source.get("datasets", [])

        lines = [
            f"## Available Datasets (Source: {source.get('name', '?')})\n",
            f"Source ID: `{SOURCE_ID}`\n",
        ]

        spatial = []
        non_spatial = []
        for d in datasets:
            geo = d.get("geometry_type", "none")
            name = d.get("name", "?")
            if geo not in (None, "none"):
                spatial.append((name, geo))
            else:
                non_spatial.append(name)

        lines.append(f"### Spatial Tables ({len(spatial)})")
        for name, geo in spatial:
            lines.append(f"- **{name}** ({geo})")

        if non_spatial:
            lines.append(f"\n### Non-Spatial Tables ({len(non_spatial)})")
            for name in non_spatial:
                lines.append(f"- {name}")

        lines.append(f"\n**To discover columns**, use run_python to create a temporary map with:")
        lines.append(f"  `SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '<table>' ORDER BY ordinal_position`")
        lines.append(f"Or: `SELECT * FROM <table> LIMIT 5` to see sample data.")

        return "\n".join(lines)

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
