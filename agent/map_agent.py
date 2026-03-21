"""
Map Builder AI Agent
=====================

A Strands agent that queries Amazon Aurora PostgreSQL (PostGIS) for
building risk data and creates interactive Felt maps.

Built on: Bedrock (Claude Sonnet) + Strands Agents SDK
Data source: Aurora PostgreSQL with PostGIS
Output: Felt map URLs
"""

from strands import Agent
from strands.models.bedrock import BedrockModel

from agent.prompts import MAP_AGENT_PROMPT
from tools.aurora_tools import (
    query_aurora,
    get_buildings_in_area,
    get_risk_summary,
)
from tools.felt_tools import (
    create_felt_map,
    upload_buildings_to_map,
    upload_geojson_to_map,
    style_by_risk_category,
    style_by_numeric_risk,
)

ALL_TOOLS = [
    # Aurora PostGIS
    query_aurora,
    get_buildings_in_area,
    get_risk_summary,
    # Felt MCP
    create_felt_map,
    upload_buildings_to_map,
    upload_geojson_to_map,
    style_by_risk_category,
    style_by_numeric_risk,
]


def create_agent() -> Agent:
    """Create the Map Builder agent.

    Uses Claude Sonnet on Amazon Bedrock.
    Queries Aurora PostGIS + creates Felt maps.
    """
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-20250514",
        region_name="us-west-2",
    )

    agent = Agent(
        model=model,
        system_prompt=MAP_AGENT_PROMPT,
        tools=ALL_TOOLS,
    )

    return agent
