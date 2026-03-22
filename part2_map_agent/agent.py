#!/usr/bin/env python3
"""
Map Builder Agent
==================

A Strands agent that can build Felt maps from any table in Aurora PostgreSQL.
It reads skill docs, discovers data schema, generates Python code, and executes it.

Usage:
    python agent.py "Show wildfire risk for Austin buildings"
    python agent.py "Map power plants in California colored by energy source"
    python agent.py "Show NJ vacant parcels with high developable percentage"
    python agent.py  # interactive mode

Env vars needed:
    FELT_API_TOKEN  — Felt API token
    AURORA_DSN      — PostgreSQL connection string
    ANTHROPIC_API_KEY or AWS credentials for Bedrock
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

from strands import Agent, tool

SKILLS_DIR = Path(__file__).parent / "skills"


def load_skills() -> str:
    skills = []
    for md in sorted(SKILLS_DIR.glob("*.md")):
        skills.append(f"# SKILL: {md.stem}\n\n{md.read_text()}")
    return "\n\n---\n\n".join(skills)


SYSTEM_PROMPT = f"""You are a map builder agent. You create interactive Felt maps from PostgreSQL data.

## How You Work
1. Read the user's request
2. First, discover what data is available by querying Aurora PostgreSQL
3. Write Python code to create a Felt map with the right data and styling
4. Execute it with run_python
5. Return the Felt map URL

## Environment Variables Available
- FELT_API_TOKEN — for felt_python
- AURORA_DSN — PostgreSQL connection string

## Python Packages Available
- psycopg2 (PostgreSQL)
- felt_python (Felt API)
- os, json, time

## Skills Reference
{load_skills()}

## Your Approach
1. **ALWAYS start by discovering the data** — query column names, types, sample values
2. **Decide the best visualization** — categorical, numeric gradient, or simple
3. **Write and execute the full pipeline** in one run_python call:
   - Query Aurora for data info (center point, distinct values, etc.)
   - Create Felt map centered on the data
   - Add source layer with SQL
   - Style it appropriately
   - Print the map URL
4. **Handle errors** — if a query fails, try to fix it

## Rules
- ALWAYS use run_python to execute code
- ALWAYS print the Felt map URL at the end
- ALWAYS discover the schema before assuming column names (especially the geometry column name!)
- ALWAYS pass api_token=token to every felt_python function call
- Source ID for all SQL queries: SUdIQGqeTFKqkHrx9AYVPDA
- Use schema-qualified table names (e.g., public.building_risk, broadband.power_plants_ca)
- Variables persist between run_python calls — set up imports and token once, reuse them
- **STRONGLY PREFER** writing the FULL pipeline in ONE run_python call. Do NOT split into multiple calls.
  The pattern is: discover schema → create map → add source layer → wait → list layers → style → print URL.
  All in one code block. Multiple calls cause auth issues.
"""


_exec_globals = {"__builtins__": __builtins__}


@tool
def run_python(code: str) -> str:
    """Execute Python code and return stdout/stderr.

    Use this to query Aurora PostgreSQL and create Felt maps.
    Available: psycopg2, felt_python, os, json, time.
    Env vars: AURORA_DSN, FELT_API_TOKEN.

    Variables persist between calls — you can define something in one call
    and use it in the next.

    Args:
        code: Python code to execute.

    Returns:
        Combined stdout and stderr from execution.
    """
    import io
    import contextlib

    stdout = io.StringIO()
    stderr = io.StringIO()
    # Log code being executed
    print(f"--- EXECUTING ---\n{code}\n--- END CODE ---", file=sys.stderr)
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
    """Get the best available model — Anthropic API or Bedrock."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        from strands.models.anthropic import AnthropicModel
        return AnthropicModel(
            model_id="claude-sonnet-4-20250514",
        )
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
        tools=[run_python],
    )


def main():
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        print("🗺️  Map Builder Agent")
        print("=" * 50)
        print("Build Felt maps from any database table.\n")
        print("Examples:")
        print('  "Show wildfire risk for Austin buildings"')
        print('  "Map power plants in California by energy source"')
        print('  "Show schools in Victoria Australia by type"')
        print('  "Map NJ parcels with high land value"')
        print('  "What data is available?"')
        print()
        prompt = input("🔍 > ").strip()
        if not prompt:
            sys.exit(0)

    print(f"\n🤖 Working on: {prompt}\n")
    agent = create_agent()
    result = agent(prompt)
    print(f"\n{'='*50}\n✅ Done!")


if __name__ == "__main__":
    main()
