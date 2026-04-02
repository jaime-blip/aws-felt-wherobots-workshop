# From Satellite to Signal
### Building a Geospatial Agentic AI Stack on AWS

**Presented by Felt, Wherobots, and AWS**
90-minute hands-on workshop

> Turn raw geospatial data into intelligence — powered by Amazon Aurora PostgreSQL with PostGIS, Wherobots, and Felt. Build a production-ready pipeline that combines spatial joins, analytics, and AI agent orchestration.

## What You'll Build

**Part 1 — Agentic Data Engineering** (Wherobots MCP)
- Ingest MODIS satellite flood data, NOAA severe weather events, USFS wildfire risk
- Medallion architecture: Bronze → Silver → Gold
- Composite risk scoring per building
- JDBC export to Amazon Aurora PostgreSQL

**Part 2 — Map Builder AI Agent** (Aurora + Felt MCP)
- Set up Felt MCP tools for map creation & styling
- Connect Aurora as a spatial data source
- Build a Strands agent that turns prompts into Felt maps
- "Show wildfire risk for San Diego buildings" → map URL

## Architecture

See `CLAUDE.md` for full architecture diagram and build plan.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in credentials
```

## Stack

- **Amazon Bedrock** (Claude Sonnet) + **Strands Agents SDK**
- **Wherobots Cloud** (Apache Sedona) + **Wherobots MCP**
- **Amazon Aurora PostgreSQL 17** with PostGIS
- **Felt** + **Felt MCP**
