# 🌍 AWS Geospatial AI Workshop

**Agentic GIS: From Satellite Data to Interactive Maps with AI**

A hands-on workshop combining Wherobots (spatial data engineering), Aurora weather forecasting, and Felt (AI-native mapping) — all orchestrated by an AI agent built with AWS Strands Agents SDK.

## Workshop Structure

### Half 1: Data Engineering with Wherobots (45 min)
Wrangle MODIS satellite imagery and earth observation datasets for climate risk analysis.

| Step | Script | Description |
|------|--------|-------------|
| 1 | `notebooks/01_wherobots_setup.py` | Connect to Wherobots Cloud (Apache Sedona) |
| 2 | `notebooks/02_load_modis.py` | Load MODIS satellite flood data |
| 3 | `notebooks/03_load_datasets.py` | Load NOAA storms, USFS wildfire, Overture buildings |
| 4 | `notebooks/04_process_enrich.py` | Spatial joins & composite risk scoring |
| 5 | `notebooks/05_export_results.py` | Export enriched data for the agent |

### Half 2: Building a Strands Agent (45 min)
Build an AI agent that calls weather models and publishes to Felt maps.

| Step | Script | Description |
|------|--------|-------------|
| 6 | `tools/aurora_tools.py` | Weather forecasting tools (Open-Meteo + Aurora) |
| 7 | `tools/felt_tools.py` | Felt MCP tools for map creation & styling |
| 8 | `agent/climate_agent.py` | The Strands Agent combining all tools |
| 9 | `main.py` | Demo CLI — natural language → risk maps |

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Earth Obs Data  │     │  Wherobots Cloud │     │    Felt      │
│                  │     │  (Apache Sedona) │     │  (Maps API)  │
│ MODIS Flood      │────▶│                  │────▶│              │
│ NOAA Storms      │     │  Spatial SQL     │     │  Interactive │
│ USFS Wildfire    │     │  Raster Ops      │     │  Risk Maps   │
│ Overture Bldgs   │     │  Risk Scoring    │     │              │
└──────────────────┘     └──────────────────┘     └──────────────┘
                                │                        ▲
                       ┌────────▼────────┐               │
                       │  Strands Agent  │───────────────┘
                       │  (Claude on     │
                       │   Bedrock)      │
                       │                 │
                       │  Tools:         │
                       │  • Wherobots    │
                       │  • Aurora/Wx    │
                       │  • Felt MCP     │
                       └─────────────────┘
```

## Prerequisites

- Python 3.10+
- AWS account with Bedrock access (Claude Sonnet)
- Wherobots Cloud account (cloud.wherobots.com)
- Felt account + API token (felt.com/account/integrations)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your credentials
```

## Quick Demo

```bash
# Run the agent
python main.py "Show me wildfire risk for buildings in LA county"
python main.py "What's the flood risk in Houston with this week's forecast?"
python main.py "Create a climate risk map of Miami-Dade county"
```

## Stack

- **[AWS Strands Agents SDK](https://github.com/strands-agents/sdk-python)** — Agent framework
- **[Amazon Bedrock](https://aws.amazon.com/bedrock/)** — Claude Sonnet LLM
- **[Wherobots Cloud](https://wherobots.com)** — Spatial data processing (Apache Sedona)
- **[Aurora](https://www.microsoft.com/en-us/research/publication/aurora-a-foundation-model-of-the-atmosphere/)** — Weather foundation model (1.3B params)
- **[Felt](https://felt.com)** — AI-native collaborative maps
- **[Open-Meteo](https://open-meteo.com)** — Free weather API

## Partners

Built by **Felt** in collaboration with **AWS** and **Wherobots**.
