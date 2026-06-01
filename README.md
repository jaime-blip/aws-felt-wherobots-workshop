# From Satellite to Signal
### Building a Geospatial Agentic AI Stack on AWS

**Presented by Felt, Wherobots, and AWS**
90-minute hands-on workshop

> An end-to-end workflow that takes raw satellite imagery and weather data through agentic data engineering, risk scoring, and into interactive map dashboards — all driven by natural language.

---

## The Data Story

**1,035,306 San Diego buildings** scored for wildfire, flood, and severe weather risk across 4 industry verticals (insurance, commercial real estate, capital markets, energy). The wildland-urban interface near Poway and Ramona — where the 2003 Cedar Fire and 2007 Witch Creek Fire devastated neighborhoods — is where risk concentrates. Same buildings, different scores depending on who's asking.

---

## What You'll Build

**Part 1 — Agentic Data Engineering** (Wherobots MCP)
- Explore satellite and weather data catalogs via the Wherobots MCP server
- Walk through a medallion pipeline (Bronze → Silver → Gold) that scores buildings using zonal statistics, KNN spatial joins, and temporal aggregation
- Verify 4 Gold tables in Aurora PostgreSQL with industry-specific risk tiers

**Part 2 — Map Builder AI Agent** (Strands + Bedrock + Felt MCP)
- Run a Strands agent that reads skill docs, generates Python, and executes it
- Create interactive Felt maps from natural language: *"Show buildings with high wildfire risk near Poway"*
- Explore the same data through the Felt MCP for conversational map creation

## Architecture

```
Part 1: Data Engineering Agent          Part 2: End-User Map Agent
─────────────────────────────           ──────────────────────────
Developer in Claude Code / Kiro         Strands Agent (Bedrock Claude)
        │                                       │
        ▼                                       ▼
┌─────────────────────┐               ┌───────────────────────┐
│ Wherobots MCP       │               │ Skills + python_repl  │
│ Spatial SQL on      │               │ + Felt MCP            │
│ Apache Sedona       │               │ (felt.com/mcp)        │
└────────┬────────────┘               └───────────┬───────────┘
         │                                        │
         ▼                                        ▼
   Bronze → Silver → Gold               ┌──────────────────┐
         │                               │ Felt Maps        │
         │ JDBC                          │ Interactive,     │
         ▼                               │ shareable,       │
┌──────────────────┐                     │ live from Aurora  │
│ Aurora PostgreSQL ├────────────────────▶│                  │
│ workshop schema  │                     └──────────────────┘
│ ~1M × 4 tables   │
└──────────────────┘
```

> See [architecture.md](architecture.md) for the full architecture with data sources, layer details, and design decisions.

---

## Get Started

👉 **Go straight to the [step-by-step workshop guide](workshop-step-by-step.md).**

It walks you through everything in order — setup (clone, credentials, MCP configuration), then the full 90-minute hands-on workshop from Part 1 (data engineering) through Part 2 (the map agent).

---

## Repository Structure

```
├── architecture.md                    # Two-part architecture diagram + design decisions
├── workshop-step-by-step.md           # 90-minute workshop guide
├── abstract.md                        # Workshop abstract
├── .env.example                       # Credential template
│
├── part1_data_engineering/
│   ├── bronze-to-silver.ipynb         # Spatial joins, zonal stats, KNN (generated via MCP)
│   ├── silver-to-gold.ipynb           # Industry scoring, risk tiers (generated via MCP)
│   ├── aurora_schema.sql              # Aurora DDL reference
│   ├── data_dictionary.md             # Full schema + business logic for all 15 tables
│   └── skills/wherobots-pipeline/     # Skill that guides MCP toward deterministic output
│
├── part2_map_agent/
│   ├── agent.py                       # Strands Agent (Bedrock Claude + skills + python_repl)
│   ├── run.sh                         # Agent launcher
│   ├── requirements.txt               # Python dependencies
│   ├── skills/
│   │   ├── aurora-postgis/            # Skill: PostGIS query patterns
│   │   └── felt-mapping/              # Skill: Felt map creation + FSL styling
│   └── evals/                         # LLM-as-judge evaluation framework
│
├── deploy-aurora/
│   ├── cloudformation.yaml            # Aurora + VPC + Bedrock IAM (provisioning)
│   └── README.md                      # Deploy / tear-down instructions
│
├── scripts/
│   ├── bootstrap.py                   # Wherobots org_catalog ingest (Bronze)
│   ├── run_bootstrap.py               # Local wrapper that submits bootstrap.py
│   ├── upload_seed_to_s3.sh           # Refreshes the Aurora seed file in S3
│   └── dump_gold_tables.py            # Authoring tool: snapshot gold tables → CSV + DDL
│
└── tmp/                               # Dev-only scripts (not part of workshop)
```

---

## Stack

| Component | Technology | Role |
|-----------|-----------|------|
| **Data Processing** | Wherobots Cloud (Apache Sedona) + Wherobots MCP | Spatial SQL, medallion pipeline |
| **Data Store** | Amazon Aurora PostgreSQL 17 + PostGIS | Gold layer serving, spatial queries |
| **AI Orchestration** | Amazon Bedrock (Claude Opus 4.8) + Strands Agents SDK | Agent that generates and executes Python |
| **Visualization** | Felt + Felt MCP (`felt.com/mcp`) | Interactive maps, styling, sharing |
| **Infrastructure** | Amazon S3, AWS IAM, CloudFormation | Storage, auth, provisioning |

---

## Links

- [Workshop Guide](workshop-step-by-step.md) — Full 90-minute step-by-step
- [Architecture](architecture.md) — Two-part diagram, data sources, design decisions
- [Felt API](https://developers.felt.com/rest-api/api-reference) — REST API reference
- [Felt MCP](https://felt.com/mcp) — MCP server for conversational map creation
- [felt-python SDK](https://github.com/felt/felt-python) — Python wrapper
- [Strands Agents SDK](https://github.com/strands-agents/sdk-python) — Agent framework
- [Wherobots Cloud](https://www.wherobots.com/) — Managed Apache Sedona
- [Wherobots MCP](https://docs.wherobots.com/develop/mcp/mcp-server-setup.md) — MCP server docs
- [Amazon Bedrock](https://docs.aws.amazon.com/bedrock/) — Foundation model hosting
