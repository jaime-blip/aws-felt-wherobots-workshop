# 🌍 AWS Geospatial AI Workshop

**Agentic GIS: From Satellite Data to Interactive Maps with AI**

A hands-on workshop combining Wherobots MCP (agentic data engineering), Amazon Aurora PostgreSQL/PostGIS (spatial database), and Felt MCP (AI-native mapping) — all orchestrated by AI agents built with AWS Strands SDK.

## Workshop Structure

### Part 1 — Agentic Data Engineering (Wherobots MCP) ⏱️ 45 min
Full AI development experience: an agent-driven data pipeline using the medallion architecture.

| Step | Script | Description |
|------|--------|-------------|
| 1 | `notebooks/01_setup.py` | Connect to Wherobots Cloud + explore catalog |
| 2 | `notebooks/02_bronze.py` | **Bronze**: Ingest raw MODIS, NOAA storms, USFS wildfire |
| 3 | `notebooks/03_silver.py` | **Silver**: Clean, normalize, spatial joins |
| 4 | `notebooks/04_gold.py` | **Gold**: Composite risk scoring per building |
| 5 | `notebooks/05_export_aurora.py` | JDBC export gold layer → Amazon Aurora PostgreSQL |

### Part 2 — Map Builder AI Agent (Aurora + Felt MCP) ⏱️ 45 min
Build a Strands agent that queries Aurora and creates Felt maps.

| Step | Script | Description |
|------|--------|-------------|
| 6 | `tools/felt_tools.py` | Felt MCP tools + skills for map creation & styling |
| 7 | `tools/aurora_tools.py` | Aurora PostGIS query tools + spatial filtering |
| 8 | `agent/map_agent.py` | Strands agent wiring Aurora + Felt tools |
| 9 | `main.py` | Demo: "Show wildfire risk for Austin buildings" → Felt map URL |

## Architecture

```
         Part 1: Agentic Data Engineering              Part 2: Map Builder Agent
    ┌─────────────────────────────────────────┐    ┌───────────────────────────────┐
    │                                         │    │                               │
    │  ┌──────────┐   Wherobots MCP           │    │   Strands Agent (Bedrock)     │
    │  │ MODIS    │──┐  (Apache Sedona)       │    │         │                     │
    │  │ NOAA     │──┤                        │    │    ┌────┴────┐                │
    │  │ USFS     │──┤  ┌───────┐  ┌───────┐ │    │    │         │                │
    │  │ Overture │──┘  │Bronze │→ │Silver │ │    │  Aurora    Felt               │
    │  └──────────┘     │ raw   │  │ clean │ │    │  PostGIS   MCP               │
    │                   └───────┘  └───┬───┘ │    │  Tools     Tools             │
    │                              ┌───▼───┐ │    │    │         │                │
    │                              │ Gold  │ │    │    ▼         ▼                │
    │                              │ scored│─┼────┼→ Aurora   Felt Map            │
    │                              └───────┘ │    │  (PostGIS)  URL              │
    │                                JDBC    │    │                               │
    └─────────────────────────────────────────┘    └───────────────────────────────┘
```

## Prerequisites

- Python 3.10+
- AWS account with Bedrock access (Claude Sonnet) + Aurora PostgreSQL cluster
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
python main.py "Show wildfire risk for buildings in Austin"
python main.py "Map flood risk in Houston with critical buildings highlighted"
python main.py "Which Miami buildings have composite risk above 0.7?"
```

## Stack

- **[AWS Strands Agents SDK](https://github.com/strands-agents/sdk-python)** — Agent framework
- **[Amazon Bedrock](https://aws.amazon.com/bedrock/)** — Claude Sonnet LLM
- **[Amazon Aurora PostgreSQL](https://aws.amazon.com/rds/aurora/)** — Spatial database (PostGIS)
- **[Wherobots Cloud](https://wherobots.com)** — Spatial data engineering (Apache Sedona)
- **[Felt](https://felt.com)** — AI-native collaborative maps
- **[Felt MCP](https://github.com/feltlabs/felt-mcp)** — MCP server for Felt

## Partners

Built by **Felt** in collaboration with **AWS** and **Wherobots**.
