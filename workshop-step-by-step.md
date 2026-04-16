# Building a Geospatial Agentic AI Stack on AWS — Workshop Guide

**Turn raw geospatial data into intelligence.** Powered by Amazon Aurora PostgreSQL (PostGIS), Wherobots, and Felt.

**Duration:** ~90 minutes
**Level:** Intermediate (comfortable with Python & command line)

---

## What You'll Build

An end-to-end geospatial AI pipeline that scores **358,985 San Diego buildings** for wildfire, flood, and severe weather risk — then lets you explore them through natural language prompts that generate interactive maps.

**Part 1 — Agentic Data Engineering** (~35 min)
Walk through a Wherobots MCP-powered medallion pipeline (Bronze → Silver → Gold) that turns satellite imagery and weather events into per-building risk scores stored in Aurora PostgreSQL.

**Part 2 — Map Builder AI Agent** (~40 min)
Run an AI agent that takes prompts like *"Show me buildings with high wildfire risk near Poway"* and creates styled, interactive Felt maps — powered by Strands Agents SDK, Amazon Bedrock (Claude), and Felt.

---

## The Data Story

San Diego County sits at the intersection of three natural hazards:

- **Wildfire** — The eastern hills (Poway, Ramona, Cleveland National Forest edge) are the wildland-urban interface where the 2003 Cedar Fire and 2007 Witch Creek Fire devastated neighborhoods. **140 buildings** score as elevated wildfire risk (avg wildfire_factor: 0.62).
- **Severe weather** — Santa Ana wind events and occasional hail affect **84% of all buildings** at some level.
- **Flood** — Rare but catastrophic. A single building scores as the highest-risk asset in the entire dataset.

The same building gets **different risk scores** depending on who's asking:
- An **insurer** weights wildfire and flood equally (0.40/0.40) — they care about claims
- A **real estate investor** weights severe weather highest (0.35) — they care about long-term value
- An **energy company** weights wildfire at 0.40 — they care about grid infrastructure near vegetation

This is what you'll explore: 358K buildings, 4 industry perspectives, one map.

---

## Prerequisites

### Accounts & API Keys

| What | Where to get it | Used in |
|---|---|---|
| **Felt account** | [felt.com](https://felt.com) | Part 1 + 2 |
| **Felt API token** | Felt → Settings → Integrations — starts with `felt_pat_...` | Part 2 |
| **Wherobots account** | [cloud.wherobots.com](https://cloud.wherobots.com) | Part 1 |
| **Wherobots API key** | Wherobots Console → API Keys | Part 1 |
| **AWS account** | Pre-provisioned for the workshop | Part 1 + 2 |
| **Aurora PostgreSQL** | Pre-provisioned for the workshop | Part 1 + 2 |
| **AWS Bedrock model access** | Pre-provisioned (Claude Sonnet in `us-west-2`) | Part 2 |

> **Note:** For instructor-led workshops, API keys and AWS accounts are pre-provisioned. For self-service, follow the links above to create accounts.

### Software

| What | Version | Check with |
|---|---|---|
| Python | 3.10+ | `python3 --version` |
| pip | latest | `pip --version` |
| git | any | `git --version` |
| AWS CLI | v2 | `aws --version` |
| Kiro IDE | latest | [kiro.dev](https://kiro.dev) (optional, recommended) |
| Wherobots Extension | latest | Install via `kiro --install-extension wherobots.wherobotsjobsubmit` |

---

## Setup (~10 min)

### Step 1 — Clone & install

```bash
git clone https://github.com/jaime-blip/aws-felt-wherobots-workshop.git
cd aws-felt-wherobots-workshop
python3 -m venv .venv
source .venv/bin/activate
pip install -r part2_map_agent/requirements.txt
```

### Step 2 — Configure credentials

```bash
cp .env.example .env
```

Edit `.env` with your credentials (provided by the instructor or from your own accounts):

```bash
# Wherobots Cloud
WHEROBOTS_API_KEY=your-wherobots-api-key

# Amazon Aurora PostgreSQL (PostGIS)
AURORA_DSN=postgresql://user:password@your-aurora-host:5432/workshop

# Felt
FELT_API_TOKEN=your-felt-api-token
FELT_SOURCE_ID=your-felt-source-id

# AWS (for Bedrock)
AWS_PROFILE=default
AWS_DEFAULT_REGION=us-west-2
```

### Step 3 — Set up Kiro with Wherobots extension (recommended)

If you're using Kiro, install the Wherobots extension for integrated catalog browsing, AI-assisted notebook authoring, and remote compute:

1. Install: `kiro --install-extension wherobots.wherobotsjobsubmit`
2. Command Palette (Cmd+Shift+P) → **Wherobots: Set API Key** → paste your Wherobots key
3. The extension auto-configures the MCP server and Data Hub sidebar

To connect notebooks to Wherobots compute (needed for Part 1):
1. Wherobots sidebar → **Create Workspace** → set region and instance size → **Start**
2. Open a `.ipynb` file → select the Wherobots remote runtime as your kernel
3. Code now executes on Wherobots Cloud (Sedona)

> **Full guide:** [`docs/kiro-wherobots-setup.md`](docs/kiro-wherobots-setup.md) covers installation, MCP config, runtime connection, Data Hub, and troubleshooting.

### Step 4 — Configure MCP servers

Add both MCP servers to your IDE (Kiro, VS Code, or Claude Desktop):

```json
{
  "mcpServers": {
    "wherobots": {
      "url": "https://api.cloud.wherobots.com/mcp/",
      "headers": {
        "X-API-Key": "${WHEROBOTS_API_KEY}"
      }
    },
    "felt": {
      "url": "https://felt.com/mcp",
      "headers": {
        "Authorization": "Bearer ${FELT_API_TOKEN}"
      }
    }
  }
}
```

### Step 5 — Connect Felt to Aurora PostgreSQL

This step creates a **Felt data source** so the Map Builder Agent (Part 2) can query Aurora and create maps directly.

1. Open any **Map** in Felt (or create a new one)
2. Click **"Add to map"** (the **+** button in the layer panel)
3. Select **"Connect a source"** or **"New data source"**
4. Choose **PostgreSQL** from the source types
5. Enter your Aurora connection details:
   - **Host:** Your Aurora writer endpoint (from CloudFormation output `AuroraEndpoint`)
   - **Port:** `5432`
   - **Database:** `workshop`
   - **Username / Password:** From your Aurora credentials
   - **Schema:** `workshop`
6. Click **Test Connection** — you should see a green checkmark
7. Click **Save** to create the source
8. The source is now available across your workspace for any map
9. To get the **Source ID**, use the Felt API:
   ```bash
   curl -s -H "Authorization: Bearer $FELT_API_TOKEN" \
     https://felt.com/api/v2/sources | python3 -m json.tool
   ```

10. Update `.env` with your source ID:
    ```bash
    FELT_SOURCE_ID=<your-source-id>
    ```

> **For instructor-led workshops:** The Felt source is pre-configured. You'll receive the `FELT_SOURCE_ID` with your other credentials.
>
> **Network note:** Felt connects from its infrastructure to your Aurora. For the workshop, Aurora is publicly accessible with the correct security group rules. For production deployments, see `docs/felt-aurora-connection.md` for network considerations.

### Step 6 — Verify connections

**Aurora PostgreSQL:**
```bash
python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['AURORA_DSN'])
cur = conn.cursor()
cur.execute(\"SELECT tablename FROM pg_tables WHERE schemaname='workshop'\")
print('Tables:', [r[0] for r in cur.fetchall()])
conn.close()
"
```

**Expected output:**
```
Tables: ['insurance_exposure', 'cre_risk', 'capmarkets_signals', 'energy_infra_risk']
```

**Wherobots MCP:** In your MCP chat, ask:
> *"List available catalogs"*

You should see `org_catalog` and `wherobots_open_data` in the response.

**Felt MCP:** In your MCP chat, ask:
> *"What maps do I have access to?"*

You should see your Felt workspace maps listed.

---

## Part 1: Agentic Data Engineering with Wherobots MCP (~35 min)

### Overview

In this part, you'll walk through how the **Wherobots MCP server** was used to build a medallion data pipeline that transforms raw satellite and weather data into per-building risk scores. The data is already in Aurora PostgreSQL — you'll explore how it got there and what it means.

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

### Step 1 — Explore the data catalog with Wherobots MCP (10 min)

The Wherobots MCP connects to a massive catalog of geospatial data. Let's explore what's available.

**Try these prompts in your MCP chat:**

> *"What tables are available in org_catalog.noaa_swdi?"*

This shows the severe weather datasets: hail events, mesocyclone detections, and tornado vortex signatures.

> *"Describe the schema of wherobots_open_data.overture_maps_foundation.buildings_building"*

This is the Overture Maps building footprint dataset — every building polygon in the world.

> *"Show me 5 sample rows from org_catalog.noaa_swdi.hail where the geometry is within San Diego County"*

This shows actual hail events with location, severity, and timestamp.

**What you're seeing:** The Wherobots MCP queries metadata, not the full tables. Even tables with billions of rows respond instantly because it reads catalog metadata, not data.

**Available datasets:**

| Source | Catalog Table | Type | Description |
|---|---|---|---|
| Overture Buildings | `wherobots_open_data.overture_maps_foundation.buildings_building` | Vector | 358K building footprints in San Diego |
| USFS Burn Probability | `org_catalog.wildfire_risk.burn_probability_conus` | Raster | Annual burn probability grid (32 GB) |
| USFS Flame Length | `org_catalog.wildfire_risk.conditional_flame_length_conus` | Raster | Expected flame length if fire occurs |
| MODIS Flood NRT | `org_catalog.modis.MCDWD_L3_F3_NRT` | Raster | Near real-time flood extent |
| NOAA SWDI — Hail | `org_catalog.noaa_swdi.hail` | Vector | Hail events with severity |
| NOAA SWDI — Mesocyclone | `org_catalog.noaa_swdi.structure` | Vector | Mesocyclone detections |
| NOAA SWDI — TVS | `org_catalog.noaa_swdi.tvs` | Vector | Tornado vortex signatures |

### Step 2 — Walkthrough: Bronze → Silver pipeline (10 min)

Open the notebook at `part1_data_engineering/bronze-to-silver.ipynb`. This was **generated by the Wherobots MCP** using the pipeline skill (`part1_data_engineering/skills/wherobots-pipeline/SKILL.md`).

The Silver layer enriches each building with hazard data through three spatial operations:

**Wildfire exposure** — Zonal statistics (`RS_ZonalStats`):
| Input | Operation | Output |
|-------|-----------|--------|
| Overture Buildings + USFS Burn Probability raster | Extract mean/max burn probability for each building footprint | `asset_wildfire_exposure` — wildfire_factor per building |

> **Key insight:** A building near Poway might sit directly on high burn probability land, while its neighbor 200m away is shielded by a ridge. This is why nearby buildings get different scores.

**Flood exposure** — Spatial join + temporal aggregation:
| Input | Operation | Output |
|-------|-----------|--------|
| Overture Buildings + MODIS Flood NRT raster (7 dates) | Join flood tiles to buildings, aggregate across dates | `asset_flood_exposure` — max flood extent, event count, duration |

**Severe weather density** — KNN spatial join (`ST_KNN`):
| Input | Operation | Output |
|-------|-----------|--------|
| Overture Buildings + NOAA SWDI (hail, mesocyclone, TVS) | Find 10 nearest weather events within 25km | `asset_weather_density` — event counts at 5km and 25km thresholds |

> **Try it yourself:** Ask the Wherobots MCP: *"How many hail events occurred within 25km of downtown San Diego (32.72, -117.16) in the past year?"*

### Step 3 — Walkthrough: Silver → Gold scoring (5 min)

Open the notebook at `part1_data_engineering/silver-to-gold.ipynb`. This applies a **4-step scoring framework**:

**1. Normalize** — Min-max scale each hazard metric to [0, 1]
**2. Weight** — Apply industry-specific weights:

| Industry | Wildfire | Flood | Severe Weather | Why this weighting? |
|---|---|---|---|---|
| Insurance | 0.40 | 0.40 | 0.20 | Claims are driven by fire and flood |
| Commercial Real Estate | 0.30 | 0.35 | 0.35 | Long-term value affected by all hazards |
| Capital Markets | 0.20 | 0.30 | 0.50 | Operational disruption from weather events |
| Energy & Utilities | 0.40 | 0.20 | 0.40 | Grid infrastructure near vegetation and storm paths |

**3. Classify** — Assign risk tiers:

| Tier | Score Range |
|---|---|
| High | ≥ 0.60 |
| Elevated | 0.40 – 0.59 |
| Moderate | 0.20 – 0.39 |
| Low | < 0.20 |

**4. Derive** — Compute industry-specific metrics (e.g., `triage_priority`, `outage_probability`)

**The weighting matters:** The energy table shows **274,553 buildings as "elevated"** (vs only 140 for insurance) because energy weights both wildfire and weather at 0.40, pushing more buildings above the 0.40 threshold.

> 📖 See `part1_data_engineering/data_dictionary.md` for the full schema and business logic of every table.

### Step 4 — Verify the Gold tables in Aurora (10 min)

The Gold tables were exported to Aurora PostgreSQL via JDBC. Let's verify and explore them.

**Check row counts:**
```bash
python3 -c "
import psycopg2, os
from dotenv import load_dotenv
load_dotenv()
conn = psycopg2.connect(os.environ['AURORA_DSN'])
cur = conn.cursor()
for table in ['insurance_exposure', 'cre_risk', 'capmarkets_signals', 'energy_infra_risk']:
    cur.execute(f'SELECT COUNT(*) FROM workshop.{table}')
    print(f'workshop.{table}: {cur.fetchone()[0]:,} rows')
conn.close()
"
```

**Expected output:**
```
workshop.insurance_exposure: 358,985 rows
workshop.cre_risk: 358,985 rows
workshop.capmarkets_signals: 358,985 rows
workshop.energy_infra_risk: 358,985 rows
```

**Explore the risk distribution:**

Ask the Felt MCP (or run these SQL queries directly):

> *"Query the Workshop Aurora data source: show me the risk tier distribution for insurance_exposure — count of buildings and average score per tier"*

You should see:

| Tier | Buildings | Avg Score | Dominant Driver |
|------|----------|-----------|-----------------|
| high | 1 | 0.600 | Flood + severe weather |
| elevated | 140 | 0.447 | Wildfire (avg 0.62) |
| moderate | 274,613 | 0.201 | Severe weather |
| low | 84,231 | 0.064 | Low all factors |

**What to notice:**
- Most buildings score `low` or `moderate` — San Diego's risk is **localized, not widespread**
- The **140 elevated buildings** cluster near Poway and Ramona — the wildland-urban interface where dry brush meets residential development
- **84% of buildings** have significant severe weather exposure (Santa Ana winds, occasional hail) — that's the baseline
- Different industry tables weight the **same hazards differently** — a building that's `elevated` for insurance may be only `moderate` for CRE

> **Try it:** *"Query Workshop Aurora: what are the top 10 buildings by risk_score in workshop.insurance_exposure? Show asset_id, risk_score, wildfire_factor, flood_factor, and severe_weather_factor"*

### Key Takeaways — Part 1

- **Wherobots MCP** gives you an AI-accessible interface to spatial data catalogs and processing — you didn't write Sedona code by hand
- The **medallion architecture** (Bronze → Silver → Gold) separates raw ingestion from enrichment from business scoring
- **Spatial operations** (zonal stats, KNN joins) run server-side on Apache Sedona — even billions of rows
- **JDBC export** moves Gold tables directly from Wherobots to Aurora in minutes
- The same data pipeline supports **4 different industry verticals** with different scoring weights from identical source data
- The risk story is **localized**: 140 buildings at the wildfire edge tell a different story than the 274K moderate-risk buildings downtown

---

## Part 2: Map Builder AI Agent (~40 min)

### Overview

Now let's make the data visual. You'll run an AI agent that turns natural language prompts into interactive Felt maps. The agent:

1. Reads **skill documents** (.md files) that teach it how to use PostGIS and the Felt API
2. Uses **Amazon Bedrock (Claude)** to interpret prompts and generate Python code
3. Executes code via **python_repl** to query Aurora and create styled Felt maps
4. Returns a shareable map URL

This is NOT a traditional tool-calling agent with hardcoded functions — it reads documentation, writes code, and executes it.

### Architecture

```
User: "Show me buildings with high wildfire risk near Poway"
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

### Step 1 — Navigate to the agent and understand the skills (5 min)

```bash
cd part2_map_agent
```

The agent has two skills in `skills/`:

**`aurora-postgis/SKILL.md`** — Teaches the agent how to:
- Connect to Aurora PostgreSQL via `psycopg2`
- Discover spatial tables and columns
- Run PostGIS spatial queries (bounding box, distance, joins)

**`felt-mapping/SKILL.md`** — Teaches the agent how to:
- Create Felt maps with `felt_python.create_map()`
- Add source layers from Aurora with SQL queries
- Apply FSL (Felt Style Language) for categorical and numeric styling
- Use helpers: `wait_for_layer()`, `categorical_style()`, `numeric_style()`

The agent reads these skills at runtime, then generates and executes the appropriate Python code. No hardcoded tool wrappers.

### Step 2 — Run the agent: your first map (10 min)

```bash
./run.sh "Show me buildings with elevated and high insurance risk in San Diego, colored by risk tier"
```

Or interactive mode:
```bash
./run.sh
```

**What happens behind the scenes:**
1. The agent knows the full schema (baked into its system prompt)
2. It activates the `felt-mapping` skill for styling instructions
3. Generates Python that:
   - Creates a new Felt map centered on San Diego
   - Adds a source layer with SQL: `SELECT * FROM workshop.insurance_exposure WHERE risk_tier IN ('elevated','high') LIMIT 5000`
   - Waits for the layer to process
   - Applies categorical styling on `risk_tier` (red = high, orange = elevated)
   - Renames the layer to something meaningful
4. Returns the Felt map URL

Open the URL — you should see ~141 building polygons clustered in the hills east of Poway and Ramona.

> **Note:** Risk tiers in the data are: `low`, `moderate`, `elevated`, `high`. There is no "critical" tier.

### Step 3 — Try more prompts (15 min)

Each prompt below shows what the agent does under the hood so you can follow along:

**Different industry, same buildings:**
```bash
./run.sh "Create a map showing CRE risk scores as a gradient from green to red"
```
> *Queries `workshop.cre_risk`. Applies `numeric_style("risk_score")` to create a continuous color ramp. Compare this with the insurance map — the same buildings get different colors because CRE weights severe weather more heavily.*

**Wildfire-specific view:**
```bash
./run.sh "Map energy infrastructure with high outage probability, styled by vegetation encroachment risk"
```
> *Queries `workshop.energy_infra_risk WHERE outage_probability > 0.5`. Styles by `vegetation_encroachment_risk`. Shows buildings near dry brush zones in eastern San Diego where power lines meet wildfire fuel.*

**Spatial query (PostGIS in action):**
```bash
./run.sh "Show me the 100 highest-risk buildings within 5km of downtown San Diego"
```
> *Triggers a `ST_DWithin` spatial query on `workshop.insurance_exposure`, filtering to a 5km radius around downtown (approx. -117.16, 32.72). Expect ~100 markers in the urban core — mostly moderate risk from severe weather, not wildfire.*

**Multi-layer comparison:**
```bash
./run.sh "Create a map with two layers: high insurance risk buildings in red, and the same buildings showing their CRE risk tier"
```
> *Creates one map, adds two source layers from different Gold tables. Uses `wait_for_layer(map_id, expect_count=N)` to sync each layer. Shows how the same physical buildings are scored differently by different industries.*

**The wildfire story:**
```bash
./run.sh "Map all buildings near Poway with wildfire_factor above 0.3, styled by wildfire_factor as a heat gradient"
```
> *Queries `workshop.insurance_exposure WHERE wildfire_factor > 0.3`. These are the 159 buildings at the wildland-urban interface. The gradient shows which specific buildings face the highest burn probability — and you can overlay this with the burn probability raster to see why.*

### Step 4 — Explore the Felt map (5 min)

Each map URL opens an interactive Felt map where you can:
- **Hover** over buildings to see risk scores and factor breakdowns
- **Filter** layers by attributes (e.g., show only `risk_tier = 'high'`)
- **Toggle** the burn probability raster layer to see raw wildfire data beneath
- **Share** the map URL with anyone — no login required to view
- **Add annotations** — draw, add text, mark up areas of interest

### Step 5 — Bonus: Felt MCP for conversational map exploration (5 min)

The Strands agent builds maps programmatically. But you can also explore data conversationally through the **Felt MCP** (`https://felt.com/mcp`).

If you have Felt MCP configured (from Setup Step 3), try asking in your MCP chat:

> *"Create a new map called 'Workshop Risk Explorer'. Add a layer from the Workshop Aurora data source showing buildings where wildfire_factor > 0.5, styled categorically by risk_tier."*

Or query existing map data:

> *"What's the average risk score by building_class for buildings in the elevated tier?"*

This is the **business user** path — no Python, no agent code. Just natural language to maps.

### Key Takeaways — Part 2

- The agent model is **skills + code execution** — not hardcoded tool wrappers
- **AgentSkills** (.md files) teach the agent domain knowledge at runtime
- The agent handles complex multi-step workflows: query → create map → style → screenshot
- **Felt source layers** connect directly to Aurora — maps stay live as data updates
- **Felt MCP** provides a conversational interface for business users without code
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
| **Visualization** | Felt + Felt MCP | Interactive maps, styling, sharing, conversational exploration |

**Two modes of interaction:**
- **Developer** — Strands agent with skills + code execution (Part 2, Steps 2-4)
- **Business user** — Felt MCP or Felt's in-product AI agent (Part 2, Step 5)

**Two phases of the pipeline:**
- **Part 1** is the **data pipeline** — reproducible, automated, runs on a schedule
- **Part 2** is the **AI agent** — flexible, conversational, good for exploration and ad-hoc analysis

In production, you'd use both: pipelines to keep data fresh, agents to let anyone explore it.

---

## Next Steps

- **Productionize** — Amazon Bedrock AgentCore provides runtime, identity, memory, and monitoring for deploying agents
- **More hazards** — Add earthquake, drought, or climate projection data to the scoring model
- **Custom weights** — Modify `risk_weights.yaml` to tune scoring for your specific use case
- **AWS Marketplace** — Felt and Wherobots are available on AWS Marketplace for enterprise deployment

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `psycopg2.OperationalError: connection refused` | Check Aurora host/port/credentials in `.env` |
| `FELT_API_TOKEN not set` | Add token to `.env` |
| `AccessDeniedException` from Bedrock | Check IAM permissions + Claude model access in Bedrock console |
| Wherobots MCP not connecting | Verify API key and `https://api.cloud.wherobots.com/mcp/` URL |
| Felt MCP not connecting | Verify API token and `https://felt.com/mcp` URL |
| Felt map is empty after creation | Layer still processing — `wait_for_layer()` handles this |
| Agent generates wrong SQL | Schema is in the system prompt — check `agent.py` for table definitions |
| `ModuleNotFoundError` | Activate virtualenv: `source .venv/bin/activate` |
| Agent uses wrong source ID | Check `FELT_SOURCE_ID` in `.env` |

## Useful Links

- [Felt API Reference](https://developers.felt.com/rest-api/api-reference)
- [Felt MCP Server](https://felt.com/mcp) — connect via Claude Desktop, Kiro, or VS Code
- [felt-python SDK](https://github.com/felt/felt-python)
- [Strands Agents SDK](https://github.com/strands-agents/sdk-python)
- [Amazon Bedrock Docs](https://docs.aws.amazon.com/bedrock/)
- [Wherobots Cloud](https://www.wherobots.com/)
- [Wherobots MCP Docs](https://docs.wherobots.com/develop/mcp/mcp-server-setup.md)
- [Apache Sedona SQL Functions](https://sedona.apache.org/latest-snapshot/api/sql/Overview/)
- [PostGIS Reference](https://postgis.net/docs/reference.html)
