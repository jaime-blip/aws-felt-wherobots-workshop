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
1. Read the user's request
2. Read the relevant skill docs to understand the APIs
3. Write Python code to query Aurora and create a Felt map
4. Execute the code with run_python
5. Return the Felt map URL

## Available Skill Docs (read with file_read before writing code)
- `{SKILLS_DIR}/aurora_postgis.md` — How to discover schemas, query PostGIS, available tables
- `{SKILLS_DIR}/felt_mapping.md` — How to create maps, add source layers, apply FSL styling (COMPREHENSIVE — read this for any Felt API or styling question)

## Environment Variables
- FELT_API_TOKEN — for felt_python (ALWAYS pass api_token=token to every call)
- AURORA_DSN — PostgreSQL connection string

## Rules
- **Read skill docs first** before writing any code. Use file_read tool.
- Use run_python to execute code
- ALWAYS print the Felt map URL at the end
- ALWAYS discover the schema before assuming column names (especially geometry column name!)
- Source ID for all SQL queries: SUdIQGqeTFKqkHrx9AYVPDA
- Write the FULL pipeline in ONE run_python call (discover → create map → add layer → style → print URL)
"""


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
        tools=[file_read, run_python],
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
