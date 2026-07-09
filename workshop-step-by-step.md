# Building a Geospatial Agentic AI Stack on AWS — Workshop Guide

**Turn raw geospatial data into intelligence.** Powered by Amazon Aurora PostgreSQL (PostGIS), Wherobots, and Felt.

**Duration:** ~90 minutes
**Level:** Intermediate (comfortable with Python & command line)

---

## What You'll Build

An end-to-end geospatial AI pipeline that scores **1,035,306 San Diego buildings** for wildfire, flood, and severe weather risk — then lets you explore them through natural language prompts that generate interactive maps.

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

This is what you'll explore: ~1M buildings, 4 industry perspectives, one map.

---

## Prerequisites

### Accounts & API Keys

| What | Where to get it | Used in |
|---|---|---|
| **Felt account** | [felt.com](https://felt.com) | Part 1 + 2 |
| **Felt API token** | Felt → Settings → Integrations — starts with `felt_pat_...` | Part 2 |
| **Wherobots account** | [cloud.wherobots.com](https://cloud.wherobots.com) — org must be **Professional or Enterprise tier** (MCP access is not available on Community orgs) | Part 1 |
| **Wherobots API key** | Wherobots Console → API Keys — generate it in the Professional/Enterprise-tier org | Part 1 |
| **AWS account** | Your own AWS account with admin/CFN permissions | Part 1 + 2 |
| **Aurora PostgreSQL** | Deployed by you in **Step 2** via CloudFormation | Part 1 + 2 |
| **AWS Bedrock model access** | Enable Claude Opus 4.8 in `us-west-2` (Bedrock console → Model access) | Part 2 |

> **Note:** Each participant deploys their own AWS stack. The CloudFormation template in `deploy-aurora/cloudformation.yaml` provisions Aurora, the VPC, and the Bedrock IAM role. Follow the links above to create the Felt and Wherobots accounts.
>
> **Wherobots tier check:** the Wherobots MCP server is gated by org tier. If your API key belongs to a Community-tier org, every MCP call fails with `MCP access is not enabled for your organization` — you'll need a key from a Professional or Enterprise org (workshop instructors can provide one). Verify your tier in the Wherobots Console under **Settings → Organization** before the session.

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

## Setup (~25 min)

### Step 1 — Clone & install

> **Python 3.10+ needed.** macOS's `python3` is 3.9.6 (too old) — `brew install python@3.13`, then use `python3.13 -m venv .venv` below.

```bash
git clone https://github.com/jaime-blip/aws-felt-wherobots-workshop.git
cd aws-felt-wherobots-workshop
python3 -m venv .venv
source .venv/bin/activate
pip install -r part2_map_agent/requirements.txt
```

Verify the install:

```bash
python -c "import strands, strands_tools, felt_python; print('venv ready')"
```

A successful clone, install, and verify looks like this:

![Step 1 — clone, install, and verify the venv](screenshots/step1-clone-install.png)

### Step 2 — Deploy the AWS stack (~10 min)

Each participant deploys their own Aurora cluster, VPC, and Bedrock IAM role.
The stack also auto-seeds `workshop.insurance_exposure` so Part 2 has data to
query before Part 1's pipeline finishes.

> **Before deploying:** make sure Bedrock model access for **Claude Opus 4.8**
> (`anthropic.claude-opus-4-8`) is enabled in `us-west-2`. Bedrock console →
> *Model access* → *Manage model access*.

Deploy the stack (pick a strong password — you'll put it in `.env` next step):

```bash
aws cloudformation deploy \
  --template-file deploy-aurora/cloudformation.yaml \
  --stack-name geospatial-workshop \
  --parameter-overrides \
      DBMasterUsername=workshop_admin \
      DBMasterPassword='ChangeMe-StrongPassword123!' \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

Aurora Serverless v2 takes ~8–10 minutes to come up. Once `deploy` returns,
grab the outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name geospatial-workshop \
  --region us-west-2 \
  --query 'Stacks[0].Outputs' \
  --output table
```

Note the `AuroraEndpoint` value — you'll need it in Step 3.

The outputs table looks like this — `AuroraDSN`, `BedrockRoleArn`, `VpcId`, and `AuroraEndpoint`:

![Step 2 — deploy the stack and read its outputs](screenshots/step2-deploy-stack.png)

> **Verify the auto-seed (optional):** the stack runs a Lambda that creates the
> `workshop` schema and bulk-loads `workshop.insurance_exposure` from S3. To
> confirm:
>
> ```bash
> psql "postgresql://workshop_admin:<PASSWORD>@<AuroraEndpoint>:5432/workshop" \
>   -c "SELECT count(*) FROM workshop.insurance_exposure;"
> ```
>
> Expect ~1,035,306 rows. If empty, see `deploy-aurora/README.md` (the `AuroraSeed` Lambda log in CloudWatch will explain why).

> **Region note:** Everything in this workshop runs in `us-west-2` — Aurora,
> Wherobots, and Bedrock. Make sure your Bedrock model access (above) is enabled
> in `us-west-2`.

> **Tear-down:** `aws cloudformation delete-stack --stack-name geospatial-workshop --region us-west-2`

### Step 3 — Configure credentials

```bash
cp .env.example .env
```

Edit `.env` with the Aurora endpoint from Step 2 plus your other credentials:

```bash
# Wherobots Cloud
WHEROBOTS_API_KEY=your-wherobots-api-key

# Amazon Aurora PostgreSQL (PostGIS)
AURORA_DSN=postgresql://user:password@your-aurora-host:5432/workshop

# Felt
FELT_API_TOKEN=your-felt-api-token
# Optional — defaults to "workshop-db". Must match the source name in Felt.
FELT_SOURCE_NAME=workshop-db

# AWS (for Bedrock)
AWS_PROFILE=default
AWS_DEFAULT_REGION=us-west-2
```

### Step 4 — Set up Kiro with Wherobots extension (recommended)

If you're using Kiro, install the Wherobots extension for integrated catalog browsing, AI-assisted notebook authoring, and remote compute:

1. Install: `kiro --install-extension wherobots.wherobotsjobsubmit`
2. Command Palette (Cmd+Shift+P) → **Wherobots: Set API Key** → paste your Wherobots key
3. The extension auto-configures the MCP server and Data Hub sidebar

To connect notebooks to Wherobots compute (needed for Part 1):
1. Wherobots sidebar → **Create Workspace** → set region and instance size (**Medium** for `bronze-to-silver`, **Small** for `silver-to-gold`) → **Start**
2. Open a `.ipynb` file → select the Wherobots remote runtime as your kernel
3. Code now executes on Wherobots Cloud (Sedona)

### Step 5 — Configure MCP servers

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

> For Felt MCP setup details and IDE-specific instructions, see the [Felt MCP help doc](https://help.felt.com/felt-ai/mcp).

### Step 6 — Connect Felt to Aurora PostgreSQL

This creates a **Felt data source** named `workshop-db` so the Map Builder Agent (Part 2) — and the Felt MCP — can query Aurora and build maps directly from it.

1. In the Felt left sidebar, under **Data sources**, click **+ → New data source**.
2. Under **External**, choose **Postgres / PostGIS**.
3. Fill in the connection (use the `AuroraEndpoint` from Step 2):
   - **Source name:** `workshop-db` — must match exactly; the agent looks this name up at startup
   - **Host:** your Aurora writer endpoint · **Port:** `5432`
   - **Database:** `workshop`
   - **Username / Password:** `workshop_admin` + the password you set at deploy
   - **Schema:** leave blank (Felt searches all schemas)
   - **Access:** Public — so the whole workspace can use it
   - **IP allowlist:** Felt connects from a fixed set of U.S. IPs (shown on the right of the form); your Aurora security group must allow them — the workshop CloudFormation already does.
4. Felt connects and indexes the source — you'll see **"Authenticated to workshop-db"**, then **"Indexing source."**
5. When indexing finishes, browse **`workshop.insurance_exposure`** to preview the rows, then click **Create map** (optional — the agent can also use the source directly).

<p>
  <img src="screenshots/step6-1-new-data-source.png" width="49%" alt="Data sources → New data source" />
  <img src="screenshots/step6-2-choose-source-type.png" width="49%" alt="Choose source type — Postgres / PostGIS" />
  <img src="screenshots/step6-3-postgres-connection.png" width="49%" alt="Postgres / PostGIS connection form" />
  <img src="screenshots/step6-4-authenticated.png" width="49%" alt="Authenticated to workshop-db, indexing source" />
  <img src="screenshots/step6-5-browse-table.png" width="49%" alt="Browse workshop.insurance_exposure, then Create map" />
</p>

> **Instructor-led workshops:** the `workshop-db` source is pre-configured — nothing to set.
>
> **Network note:** Felt connects from its infrastructure to Aurora. The workshop CloudFormation makes Aurora publicly reachable and allowlists Felt's IPs.

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
OPERA DSWx-S1 ──────▶ asset_flood_exposure ─────────┤                  ──▶ cre_risk
                                                    │                  ──▶ capital_markets_signals
NOAA SWDI Hail ──┐                                  │                  ──▶ energy_asset_risk
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
| Overture Buildings | `wherobots_open_data.overture_maps_foundation.buildings_building` | Vector | ~1M building footprints in San Diego |
| USFS Burn Probability | `org_catalog.wildfire_risk.burn_probability_conus` | Raster | Annual burn probability grid (32 GB) |
| USFS Flame Length | `org_catalog.wildfire_risk.conditional_flame_length_conus` | Raster | Expected flame length if fire occurs |
| OPERA DSWx-S1 | `org_catalog.opera.dswx_s1` | Raster | Sentinel-1 SAR surface water / flood (30 m) |
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

**Flood exposure** — Weekly zonal statistics (per ISO week):
| Input | Operation | Output |
|-------|-----------|--------|
| Overture Buildings + OPERA DSWx-S1 SAR flood raster (weekly) | For each ISO week in the flood window, zonal-stat max water-classification per building → append to Iceberg | `asset_flood_exposure` — one row per (asset, week); silver-to-gold aggregates to max class, event count, duration |

**Severe weather density** — KNN spatial join (`ST_KNN`):
| Input | Operation | Output |
|-------|-----------|--------|
| Overture Buildings + NOAA SWDI (hail, mesocyclone, TVS) | Find 10 nearest weather events within 25km | `asset_weather_density` — event counts at 5km and 25km thresholds |

> **Try it yourself:** Ask the Wherobots MCP: *"How many hail events occurred within 25km of downtown San Diego (32.72, -117.16) in the past year?"*

### Step 3 — Walkthrough: Silver → Gold scoring (5 min)

Open the notebook at `part1_data_engineering/silver-to-gold.ipynb`. This applies a **4-step scoring framework**:

> **Aurora connection:** the notebook's config cell resolves the Aurora connection automatically — from the `AURORA_DSN` environment variable, or from a `.env` file in the working directory or any parent. If neither is visible to the notebook runtime (e.g., a remote Wherobots kernel), the config cell stops with a clear error — paste your `AURORA_DSN` values into the manual fallback block in that cell. This must be configured for the run, otherwise the 4 Gold tables never land in Aurora and Part 2 only sees the CloudFormation-seeded `insurance_exposure`.

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
for table in ['insurance_exposure', 'cre_risk', 'capital_markets_signals', 'energy_asset_risk']:
    cur.execute(f'SELECT COUNT(*) FROM workshop.{table}')
    print(f'workshop.{table}: {cur.fetchone()[0]:,} rows')
conn.close()
"
```

**Expected output:**
```
workshop.insurance_exposure: 1,035,306 rows
workshop.cre_risk: 1,035,306 rows
workshop.capital_markets_signals: 1,035,306 rows
workshop.energy_asset_risk: 1,035,306 rows
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

1. Connects to the **Felt MCP server** (`https://felt.com/mcp`) for map operations
2. Uses **Amazon Bedrock (Claude)** to interpret prompts and orchestrate MCP tool calls
3. Queries Aurora directly via Felt's data source connection
4. Returns a shareable map URL with an inline preview

The agent uses MCP tools directly — no code generation required for standard workflows. For complex transforms, it falls back to `python_repl`.

### Architecture

```
User: "Show me buildings with high wildfire risk near Poway"
                    │
                    ▼
        ┌───────────────────────┐
        │  Strands Agent        │
        │  (Bedrock Claude)     │
        │                       │
        │  Tools: Felt MCP      │
        │         python_repl   │
        └───────────┬───────────┘
                    │ MCP tool calls
                    ▼
        ┌───────────────────────┐
        │  Felt MCP Server      │
        │  https://felt.com/mcp │
        │                       │
        │  → Aurora (SQL)       │
        │  → Map creation       │
        │  → FSL styling        │
        └───────────┬───────────┘
                    │
                    ▼
            Felt Map URL 🗺️
```

### Prerequisites for Part 2

Part 2 runs the Strands agent locally in **the Python virtualenv you created in
Setup Step 1**. Before continuing, make sure you have it activated:

```bash
# From the repo root
source .venv/bin/activate
python -c "import strands, strands_tools; print('venv OK')"
```

If `.venv/` doesn't exist or the import errors, re-run Setup Step 1:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r part2_map_agent/requirements.txt
```

`./run.sh` auto-sources `.venv/bin/activate` for each invocation, but the venv
itself must already exist. Without it you'll see `ModuleNotFoundError: No
module named 'strands_tools'` (or similar) when the agent starts.

### Step 1 — Navigate to the agent and understand the tools (5 min)

```bash
cd part2_map_agent
```

The agent uses **Felt MCP tools** as its primary interface:

| MCP Tool | Purpose |
|----------|---------|
| `list_data_sources` | Find the Aurora database connection |
| `create_map` | Create a new Felt map |
| `create_layer_from_data_source` | Add a layer via SQL query |
| `poll_layer_processing_status` | Wait for layer to finish |
| `generate_fsl` | AI-powered style generation |
| `update_layer_properties` | Apply styles to layers |
| `render_map` | Show inline map preview |

The agent also has **fallback skills** in `skills/`:

**`felt-mapping/SKILL.md`** — Documents the MCP tool workflow and SQL patterns

**`aurora-postgis/SKILL.md`** — Fallback for direct psycopg2 access when MCP fails

### Step 2 — Run the agent: from a simple map to a stunning one (15 min)

Start the agent in **interactive mode**:

```bash
./run.sh
```

The agent will prompt you for what to map. Try this first prompt — it builds a single-layer **triage map** of the buildings an underwriter should look at first:

> **Suggested prompt:** *"As an insurance underwriter, map the high and critical risk buildings across San Diego County on a dark basemap, colored by risk tier — red for high, dark red for critical."*

**What happens behind the scenes (MCP tool calls):**
1. `list_data_sources` → finds the Aurora PostgreSQL connection
2. `create_map` → creates a new Felt map over San Diego County on a dark basemap
3. `create_layer_from_data_source` → SQL query for the high + critical risk buildings
4. `poll_layer_processing_status` → waits for the layer to finish
5. `generate_fsl` → builds a categorical style for `risk_tier`
6. `update_layer_properties` → applies the style
7. `render_map` → shows inline preview + returns URL

**What you'll see:** 21,501 buildings — and they rake across the **eastern backcountry** (Poway, Ramona, Julian), the wildland-urban interface, *not* the coast. The serious hazard sits at the county's edges: the inland critical (dark-red) buildings are wildfire-driven, while closer to the coast risk leans more on flood and severe weather. Wildfire is the escalator that pushes a building into the critical tier.

| Risk Tier | Count | On this map |
|-----------|------:|:-----------:|
| Critical  | 2,385 | 🟥 yes |
| High      | 19,116 | 🔴 yes |
| Elevated  | 66,271 | — |
| Moderate  | 920,415 | — |
| Low       | 27,119 | — |

Of ~1M buildings, only **21,501 (2%)** land in the high/critical tiers — that focus is the point of a triage map.

> **Tip:** Want to see what's driving each building's score? Ask the agent a follow-up: *"add a popup showing risk score and the wildfire, flood, and severe-weather factors."* Notice how wildfire climbs as you move inland.

<p>
  <img src="screenshots/step2-1-buildings-map.png" width="49%" alt="High & critical risk buildings across San Diego County, colored by risk tier" />
  <img src="screenshots/step2-2-building-popup.png" width="49%" alt="Building popup — risk score and the wildfire / flood / severe-weather factors" />
</p>

#### Now make it cool — a heatmap that resolves into the buildings

Stay in the same agent session and add one more layer. This is where Felt's styling shines: a single follow-up prompt turns the flat building map into a **zoom-aware** view — a glowing risk-density heatmap when you're zoomed out, the individual buildings when you zoom in.

> **Suggested prompt:** *"Now add a risk-density layer: aggregate these buildings into an H3 hexbin heatmap colored by their average risk score, with fine bins. Make the heatmap fade out as I zoom in while the buildings fade in — so I see county-wide hotspots when zoomed out and the actual buildings when zoomed in."*

**What the agent does:**
1. `create_layer_from_data_source` → a second layer of building **centroids** (`ST_Centroid`) carrying `risk_score`
2. `generate_fsl` → an **H3 hexbin** style: `aggregation: mean` of `risk_score`, fine bins (`binMode: high`), a warm heat palette (`@ylRed`)
3. `update_layer_properties` on **both** layers → a zoom **opacity ramp**: the heatmap `{"linear": [[10, 0.9], [13, 0]]}` (fades out), the buildings `{"linear": [[11, 0], [13, 0.85]]}` (fades in)
4. `render_map`

**What you'll see:** Zoomed out, the county glows with **average-risk hotspots** — the San Marcos / Poway / backcountry concentrations pop, with none of the dot-mush of 21,000 overlapping footprints. Zoom past ~z12 and the heatmap dissolves into the **actual high/critical buildings**, tier-colored and clickable. Same data, two reading altitudes — overview and detail — entirely driven by style.

> **Why it works:** the zoom behavior lives in the FSL `opacity` ramp (`{"linear": [[zoom, value], …]}`) — no special layer-visibility toggle needed. H3 bins by point location, so the heatmap queries centroids; the building layer stays polygons.

<p>
  <img src="screenshots/step2-3-h3-overview.png" width="49%" alt="Zoomed out — H3 risk-density heatmap colored by average risk score" />
  <img src="screenshots/step2-4-h3-crossfade.png" width="49%" alt="Zoomed in — hexbins dissolving into the individual buildings" />
</p>

### Step 3 — Explore with more prompts (15 min)

Continue in **interactive mode** — the agent remembers context from previous maps. Try these prompts to explore different perspectives:

---

**Spatial query (PostGIS in action):**

> *"What are the 100 highest-risk buildings within 10 miles of downtown San Diego (32.7157, -117.1611)? Show them on a map, and draw the 10-mile radius as a visible buffer circle for context."*

Triggers a `ST_DWithin` spatial query plus an `ST_Buffer` ring you can actually see (transparent fill, colored stroke). Expect ~100 markers inside the circle — mostly moderate risk from severe weather, not wildfire. The buffer makes the point visually: the worst (high/critical) buildings sit *outside* the metro ring, out in the eastern backcountry.

![Top 100 highest-risk buildings within 10 miles of downtown, with the 10-mile buffer ring](screenshots/step3-spatial-query.png)

---

**The wildfire story:**

> *"Map all buildings near Poway with wildfire_factor above 0.3. Use a heat gradient to show severity."*

These are the ~159 buildings at the wildland-urban interface. The gradient shows which specific buildings face the highest burn probability — the 2003 Cedar Fire and 2007 Witch Creek Fire swept through this exact area.

![Poway wildfire exposure — buildings with wildfire_factor > 0.3, colored by severity](screenshots/step3-wildfire-poway.png)

### Step 4 — Explore the Felt map (5 min)

Each map URL opens an interactive Felt map where you can:
- **Hover** over buildings to see risk scores and factor breakdowns
- **Filter** layers by attributes (e.g., show only `risk_tier = 'high'`)
- **Toggle** the burn probability raster layer to see raw wildfire data beneath
- **Share** the map URL with anyone — no login required to view
- **Add annotations** — draw, add text, mark up areas of interest

### Step 5 — Bonus: Felt MCP for conversational map exploration (5 min)

The Strands agent builds maps programmatically. But you can also explore data conversationally through the **Felt MCP** (`https://felt.com/mcp`).

If you have Felt MCP configured (from Setup Step 5), try asking in your MCP chat:

> *"Create a new map called 'Workshop Risk Explorer'. Add a layer from the Workshop Aurora data source showing buildings where wildfire_factor > 0.5, styled categorically by risk_tier."*

Or query existing map data:

> *"What's the average risk score by building_class for buildings in the elevated tier?"*

This is the **business user** path — no Python, no agent code. Just natural language to maps.

> New to the Felt MCP? See the [Felt MCP help doc](https://help.felt.com/felt-ai/mcp) for setup and what it can do.

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
| **Data Sources** | NOAA, USFS, OPERA (NASA), Overture Maps | Raw geospatial data |
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
| `AccessDeniedException` from Bedrock | Check IAM permissions + Claude model access in Bedrock console. The role needs `bedrock:Converse` / `bedrock:ConverseStream` (the Strands SDK uses the Converse API) in addition to `bedrock:InvokeModel*` — on AWS Workshop Studio accounts, make sure `WSParticipantRole` includes them. |
| Wherobots MCP not connecting | Verify API key and `https://api.cloud.wherobots.com/mcp/` URL |
| `MCP access is not enabled for your organization` | Your Wherobots API key belongs to a Community-tier org. Use a key from a **Professional or Enterprise** org (see Prerequisites). |
| Felt MCP not connecting | Verify API token and `https://felt.com/mcp` URL |
| Felt map is empty after creation | Layer still processing — `wait_for_layer()` handles this |
| Agent generates wrong SQL | Schema is in the system prompt — check `agent.py` for table definitions |
| `ModuleNotFoundError` | Activate virtualenv: `source .venv/bin/activate` |
| Agent can't find Felt source | Agent resolves by name (`FELT_SOURCE_NAME`, default `workshop-db`). Ensure a Felt source with that exact name is connected to Aurora. |

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
