"""
Climate Risk Agent
===================

A Strands agent that combines Wherobots (spatial data), Aurora (weather
forecasting), and Felt (mapping) to analyze and visualize climate risk.

Built on AWS: Bedrock (Claude Sonnet) + Strands Agents SDK.
"""

from strands import Agent
from strands.models.bedrock import BedrockModel

from agent.prompts import CLIMATE_AGENT_PROMPT
from tools.wherobots_tools import (
    wherobots_query,
    wherobots_count_buildings,
    wherobots_explore_catalog,
    load_risk_data,
)
from tools.aurora_tools import (
    get_weather_forecast,
    get_historical_weather,
    get_climate_risk_assessment,
)
from tools.felt_tools import (
    create_felt_map,
    upload_geojson_to_felt,
    upload_risk_data_to_felt,
    style_risk_layer,
    style_numeric_layer,
)

ALL_TOOLS = [
    # Wherobots
    wherobots_query,
    wherobots_count_buildings,
    wherobots_explore_catalog,
    load_risk_data,
    # Aurora / Weather
    get_weather_forecast,
    get_historical_weather,
    get_climate_risk_assessment,
    # Felt
    create_felt_map,
    upload_geojson_to_felt,
    upload_risk_data_to_felt,
    style_risk_layer,
    style_numeric_layer,
]


def create_agent() -> Agent:
    """Create the climate risk analyst agent.

    Uses Claude Sonnet on Amazon Bedrock via Strands SDK.
    Wired up with Wherobots + Aurora + Felt tools.
    """
    model = BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-20250514",
        region_name="us-west-2",
    )

    agent = Agent(
        model=model,
        system_prompt=CLIMATE_AGENT_PROMPT,
        tools=ALL_TOOLS,
    )

    return agent
