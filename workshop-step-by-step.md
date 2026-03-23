# Building a Geospatial Agentic AI Stack on AWS — Workshop Guide

**Turn raw geospatial data into intelligence.** Powered by Amazon Aurora PostgreSQL (PostGIS), Wherobots, and Felt.

**Duration:** ~90 minutes  
**Level:** Intermediate (comfortable with Python & command line)

---

## What You'll Build

**Part 1 — Agentic Data Engineering** (Wherobots MCP)  
Use the Wherobots MCP server to explore spatial data catalogs, run a medallion pipeline (Bronze → Silver → Gold), and write scored building risk data to Amazon Aurora PostgreSQL.

**Part 2 — Map Builder AI Agent** (Strands + Bedrock + Felt)  
Build an AI agent that takes natural language prompts like *"Show me buildings with high insurance risk in San Diego"* and creates styled, interactive Felt maps — powered by AWS Strands Agents SDK, Amazon Bedrock (Claude), and Felt's mapping API.

---

## Prerequisites

### Accounts & API Keys

| What | Where to get it | Used in |
|---|---|---|
| **Felt account** | [felt.com](https://felt.com) | Part 1 + 2 |
| **Felt API token** | [felt.com/maps/latest/integrations](https://felt.com/maps/latest/integrations) — starts with `felt_pat_...` | Part 2 |
| **Wherobots account** | [cloud.wherobots.com](https://cloud.wherobots.com) | Part 1 |
| **Wherobots API key** | Wherobots Console → API Keys | Part 1 |
| **AWS account** | [aws.amazon.com](https://aws.amazon.com) | Part 1 + 2 |
| **Aurora PostgreSQL** | Pre-provisioned for the workshop | Part 1 + 2 |
| **AWS Bedrock model access** | AWS Console → Bedrock → Model access → enable **Claude Sonnet** in `us-west-2` | Part 2 |

### Software

| What | Version | Check with |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| pip | latest | `pip --version` |
| git | any | `git --version` |
| AWS CLI | v2 (recommended) | `aws --version` |
| Kiro IDE | latest | [kiro.dev](https://kiro.dev) (optional, recommended) |

---

## Setup

### Step 1 — Clone & install

```bash
git clone https://github.com/jaime-blip/aws-felt-wherobots-workshop.git
cd aws-felt-wherobots-workshop
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 2 — Configure credentials

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Wherobots Cloud
WHEROBOTS_API_KEY=your-wherobots-api-key

# Amazon Aurora PostgreSQL (PostGIS)
AURORA_DSN=postgresql://readonly:LhxfvetErTSA2Dw8CGPakW@db3.sales.felt.com/main
POSTGRES_HOST=db3.sales.felt.com
POSTGRES_PORT=5432
POSTGRES_DB=main
POSTGRES_USER=readonly
POSTGRES_PASSWORD=LhxfvetErTSA2Dw8CGPakW

# Felt
FELT_API_TOKEN=your-felt-api-token
FELT_SOURCE_ID=rYZY3hxzTJCJnEZP2k1r0B

# AWS (for Bedrock)
AWS_PROFILE=default
AWS_DEFAULT_REGION=us-west-2
```

### Step 3 — Verify connections

**Aurora PostgreSQL:**
```bash
python3 -c "
import psycopg2
conn = psycopg2.connect('postgresql://readonly:LhxfvetErTSA2Dw8CGPakW@db3.sales.felt.com/main')
cur = conn.cursor()
cur.execute(\"SELECT tablename FROM pg_tables WHERE schemaname='workshop'\")
print('Tables:', [r[0] for r in cur.fetchall()])
conn.close()
"
```

Expected output:
```
Tables: ['insurance_exposure', 'cre_risk', 'capmarkets_signals', 'energy_infra_risk']
```

**AWS Bedrock:**
```bash
aws bedrock list-foundation-models --region us-west-2 \
  --query "modelSummaries[?contains(modelId,'claude')]" --output table
```

---

## Part 1: Agentic Data Engineering with Wherobots MCP (45 min)

### Overview

In this part, you'll use the **Wherobots MCP server** to explore spatial data catalogs and understand how raw geospatial data (satellite imagery, weather events, building footprints) gets processed through a medallion architecture into industry-scored risk tables.

### Architecture

```
Bronze (Raw Sources)          Silver (Enriched)              Gold (Industry-Scored)
──────────────────────        ────────────────────           ────────────────────────
Overture Buildings ──┐
                     ├──▶ asset_wildfire_exposure ──┐
USFS Burn Probability┤                              │
USFS Flame Length ───┘                              │
                                                    ├──▶ asset_enriched ──▶ insurance_exposure
MODIS Flood NRT ────▶ asset_flood_exposure ─────────┤                  ──▶ cre_risk
                                                    │                  ──▶ capmarkets_signals
NOAA SWDI Hail ──┐                                  │                  ──▶ energy_infra_risk
NOAA SWDI Struct ┼──▶ asset_weather_density ────────┘
NOAA SWDI TVS ───┘
                                    │
                                    ▼
                          Aurora PostgreSQL (PostGIS)
                              workshop schema
```

### Step 1 — Connect to Wherobots MCP

The Wherobots MCP is a **hosted HTTP MCP server** — not a pip package. Configure it in your IDE (Kiro, VS Code, or Claude Desktop):

```json
{
  "mcpServers": {
    "wherobots": {
      "url": "https://api.cloud.wherobots.com/mcp/",
      "headers": {
        "X-API-Key": "${WHEROBOTS_API_KEY}"
      }
    }
  }
}
```

Once connected, you can ask the MCP to explore data catalogs, generate spatial SQL, and execute queries on Wherobots Cloud (Apache Sedona).

### Step 2 — Explore the data catalog

Use the Wherobots MCP to discover available datasets:

| Source | Catalog Table | Type | Description |
|---|---|---|---|
| Overture Buildings | `wherobots_open_data.overture_maps_foundation.buildings_building` | Vector | Global building footprints |
| USFS Burn Probability | `org_catalog.wildfire_risk.burn_probability_conus` | Raster | Annual burn probability grid |
| USFS Flame Length | `org_catalog.wildfire_risk.conditional_flame_length_conus` | Raster | Expected flame length if fire occurs |
| MODIS Flood NRT | `org_catalog.modis.MCDWD_L3_F3_NRT` | Raster | Near real-time flood extent |
| NOAA SWDI — Hail | `org_catalog.noaa_swdi.hail` | Vector | Hail events with severity |
| NOAA SWDI — Structures | `org_catalog.noaa_swdi.structure` | Vector | Mesocyclone detections |
| NOAA SWDI — TVS | `org_catalog.noaa_swdi.tvs` | Vector | Tornado vortex signatures |

Try asking the MCP:
- *"What tables are available in org_catalog.noaa_swdi?"*
- *"Describe the schema of the Overture buildings table"*
- *"Show me 10 sample rows from the hail events table"*

### Step 3 — Understand the Silver layer (spatial joins)

The Silver layer enriches each building with hazard data through spatial operations:

**Wildfire exposure** — Zonal statistics (`RS_ZonalStats`) extract mean/max burn probability from USFS raster tiles overlapping each building footprint.

**Flood exposure** — MODIS flood raster tiles are spatially joined to buildings. Aggregated across dates to get max flood extent, event count, and duration.

**Severe weather density** — KNN spatial join (`ST_KNN`) finds the 10 nearest severe weather events within 25 km of each building, then aggregates counts at 5 km and 25 km thresholds.

### Step 4 — Understand the Gold layer (industry scoring)

All Gold tables start from `asset_enriched` (the unified Silver table) and apply:

1. **Min-max normalization** of each hazard metric to [0, 1]
2. **Weighted composite score** — weights vary by industry vertical:

| Industry | Wildfire | Flood | Severe Weather |
|---|---|---|---|
| Insurance | 0.40 | 0.40 | 0.20 |
| Commercial Real Estate | 0.30 | 0.35 | 0.35 |
| Capital Markets | 0.20 | 0.30 | 0.50 |
| Energy & Utilities | 0.40 | 0.20 | 0.40 |

3. **Risk tier classification:**

| Tier | Score Range |
|---|---|
| High | ≥ 0.60 |
| Elevated | 0.40 – 0.59 |
| Moderate | 0.20 – 0.39 |
| Low | < 0.20 |

4. **Industry-specific derived metrics** (e.g., insurance `triage_priority`, CRE `acquisition_screen_flag`, capital markets `disruption_probability`, energy `outage_probability`)

> 📖 See `part1_data_engineering/data_dictionary.md` for the full schema and business logic of every table.

### Step 5 — Explore the Gold tables in Aurora

The Gold tables have been written to Aurora PostgreSQL in the `workshop` schema. Let's verify:

```bash
python3 -c "
import psycopg2
conn = psycopg2.connect('postgresql://readonly:LhxfvetErTSA2Dw8CGPakW@db3.sales.felt.com/main')
cur = conn.cursor()
for table in ['insurance_exposure', 'cre_risk', 'capmarkets_signals', 'energy_infra_risk']:
    cur.execute(f'SELECT COUNT(*) FROM workshop.{table}')
    print(f'workshop.{table}: {cur.fetchone()[0]} rows')
conn.close()
"
```

Try some queries:

```sql
-- Risk tier distribution for insurance
SELECT risk_tier, COUNT(*) as buildings, ROUND(AVG(risk_score)::numeric, 3) as avg_risk
FROM workshop.insurance_exposure
GROUP BY risk_tier ORDER BY avg_risk DESC;

-- Top 20 highest-risk buildings for CRE
SELECT asset_id, building_class, risk_score, risk_tier, acquisition_screen_flag
FROM workshop.cre_risk
WHERE risk_tier IN ('elevated', 'high')
ORDER BY risk_score DESC LIMIT 20;

-- Energy infrastructure with high outage probability
SELECT asset_id, risk_score, outage_probability, vegetation_encroachment_risk
FROM workshop.energy_infra_risk
WHERE outage_probability > 0.5
ORDER BY outage_probability DESC LIMIT 20;
```

### Key Takeaways — Part 1

- **Wherobots MCP** gives you an AI-accessible interface to spatial data catalogs and processing
- The **medallion architecture** (Bronze → Silver → Gold) separates raw ingestion from enrichment from business scoring
- **Spatial operations** (zonal stats, KNN joins, distance calculations) run server-side on Apache Sedona
- **Aurora PostgreSQL (PostGIS)** serves as the production data store — queryable, indexable, and connectable to Felt
- The same data pipeline supports 4 different industry verticals with different scoring weights

---

## Part 2: Map Builder AI Agent (45 min)

### Overview

In this part, you'll build and run an AI agent that turns natural language prompts into interactive Felt maps. The agent:

1. Reads **skill documents** (.md files) that teach it how to use PostGIS and the Felt API
2. Uses **Amazon Bedrock (Claude)** to interpret prompts and generate Python code
3. Executes code via **python_repl** to query Aurora and create styled Felt maps
4. Returns a shareable map URL

This is NOT a traditional tool-calling agent with hardcoded functions — it reads documentation, writes code, and executes it.

### Architecture

```
User: "Show me buildings with high wildfire risk"
                    │
                    ▼
        ┌───────────────────────┐
        │  Strands Agent        │
        │  (Bedrock Claude)     │
        │                       │
        │  Reads: skills/*.md   │
        │  - aurora-postgis     │
        │  - felt-mapping       │
        └───────────┬───────────┘
                    │ generates Python
                    ▼
        ┌───────────────────────┐
        │  python_repl          │
        │                       │
        │  1. psycopg2 → Aurora │
        │  2. felt_python → Map │
        │  3. FSL → Styling     │
        └───────────┬───────────┘
                    │
                    ▼
            Felt Map URL 🗺️
```

### Step 1 — Understand the skills

The agent has two skills in `part2_map_agent/skills/`:

**`aurora-postgis/SKILL.md`** — Teaches the agent how to:
- Connect to Aurora PostgreSQL via `psycopg2`
- Discover spatial tables and columns
- Sample values for styling decisions
- Run PostGIS spatial queries (bounding box, distance, joins)

**`felt-mapping/SKILL.md`** — Teaches the agent how to:
- Create Felt maps with `felt_python.create_map()`
- Add source layers from Aurora with SQL queries via `add_source_layer()`
- Apply FSL (Felt Style Language) for categorical and numeric styling
- Use helper functions: `wait_for_layer()`, `categorical_style()`, `numeric_style()`, `rename_layer()`, `screenshot_map()`

The agent reads these skills at runtime, then generates and executes the appropriate Python code.

### Step 2 — Review the agent code

Open `part2_map_agent/agent.py`. Key components:

**Model** — Claude on Amazon Bedrock:
```python
BedrockModel(model_id="us.anthropic.claude-sonnet-4-20250514-v1:0", region_name="us-west-2")
```

**Tools** — `python_repl` (code execution) + `file_read` (read skill docs):
```python
agent = Agent(
    model=get_model(),
    system_prompt=SYSTEM_PROMPT,
    tools=[python_repl, file_read],
    plugins=[skills_plugin],
)
```

**Pre-seeded environment** — the agent's Python environment is pre-loaded with:
- `psycopg2`, `felt_python`, helper functions
- `TOKEN`, `SOURCE_ID`, `AURORA_DSN` credentials
- Ready to query and map immediately

### Step 3 — Run the agent

```bash
# From the project root
./run.sh "Show me buildings with high insurance risk in San Diego, colored by risk tier"
```

Or interactive mode:
```bash
./run.sh
```

**What happens behind the scenes:**
1. The agent already knows the full schema (baked into its system prompt — no discovery needed)
2. It activates the `felt-mapping` skill for styling instructions
3. Generates Python that:
   - Creates a new Felt map centered on San Diego
   - Adds a source layer with SQL: `SELECT * FROM workshop.insurance_exposure WHERE risk_tier IN ('elevated','high') LIMIT 5000`
   - Waits for the layer to process
   - Applies categorical styling on `risk_tier`
   - Renames the layer from "Workshop - CustomQuery" to something meaningful
   - Takes a screenshot
4. Returns the Felt map URL

> **Note:** Risk tiers in the data are: `low`, `moderate`, `elevated`, `high`. There is no "critical" tier.

### Step 4 — Try more prompts

```bash
# Compare risk across industry verticals
./run.sh "Create a map showing CRE risk scores as a gradient from green to red"

# Energy infrastructure analysis
./run.sh "Map energy infrastructure with high outage probability, styled by vegetation encroachment risk"

# Capital markets signals
./run.sh "Show buildings with disruption probability above 0.5, colored by supply chain vulnerability"

# Multi-layer map
./run.sh "Create a map with two layers: high insurance exposure in red, and elevated flood risk in blue"

# Spatial query
./run.sh "Show me the 100 highest-risk buildings within 5km of downtown San Diego"
```

### Step 5 — Explore the Felt map

Each map URL opens an interactive Felt map where you can:
- **Hover** over buildings to see risk scores and explanations
- **Filter** layers by attributes
- **Share** the map URL with anyone — no login required to view
- **Add annotations** — draw, add text, upload more data
- **Embed** the map in dashboards or reports

### Key Takeaways — Part 2

- The agent model is **skills + code execution** — not hardcoded tool wrappers
- **AgentSkills** (.md files) teach the agent domain knowledge at runtime
- The agent can handle complex multi-step workflows: discover → query → create map → style → screenshot
- **Felt source layers** connect directly to Aurora — maps stay live as data updates
- Natural language makes spatial analysis accessible to non-technical users

---

## Putting It Together

Part 1 and Part 2 form a complete geospatial AI stack:

| Layer | Technology | Role |
|---|---|---|
| **Data Sources** | NOAA, USFS, MODIS, Overture Maps | Raw geospatial data |
| **Spatial Processing** | Wherobots Cloud (Apache Sedona) | Spatial joins, zonal stats, risk scoring |
| **Data Store** | Amazon Aurora PostgreSQL (PostGIS) | Production database with spatial indexing |
| **AI Orchestration** | AWS Strands Agents SDK + Amazon Bedrock | Natural language → code generation → execution |
| **Visualization** | Felt | Interactive maps, styling, sharing |

The difference between the two parts:
- **Part 1** is the **data pipeline** — reproducible, automated, runs on a schedule
- **Part 2** is the **AI agent** — flexible, conversational, good for exploration and ad-hoc analysis

In production, you'd use both: pipelines to keep data fresh, agents to let anyone explore it.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `psycopg2.OperationalError: connection refused` | Check Aurora host/port/credentials in `.env` |
| `FELT_API_TOKEN not set` | Add token to `.env` — get one at felt.com/maps/latest/integrations |
| `AccessDeniedException` from Bedrock | Check IAM permissions + enable Claude model access in Bedrock console |
| Wherobots MCP not connecting | Verify API key and `https://api.cloud.wherobots.com/mcp/` URL |
| Felt map is empty after creation | Layer still processing — `wait_for_layer()` handles this, wait a few seconds |
| Agent generates wrong SQL | Schema is baked into the system prompt — check `agent.py` for the table definitions |
| `ModuleNotFoundError` | Activate virtualenv: `source .venv/bin/activate` |
| Agent uses wrong source ID | Check `FELT_SOURCE_ID` in `.env` — should point to the Workshop source |

## Useful Links

- [Felt API Reference](https://developers.felt.com/rest-api/api-reference)
- [felt-python SDK](https://github.com/felt/felt-python)
- [Strands Agents SDK](https://github.com/strands-agents/sdk-python)
- [Amazon Bedrock Docs](https://docs.aws.amazon.com/bedrock/)
- [Wherobots Cloud](https://www.wherobots.com/)
- [Wherobots MCP Docs](https://docs.wherobots.com/develop/mcp/mcp-server-setup.md)
- [Apache Sedona SQL Functions](https://sedona.apache.org/latest-snapshot/api/sql/Overview/)
- [PostGIS Reference](https://postgis.net/docs/reference.html)
