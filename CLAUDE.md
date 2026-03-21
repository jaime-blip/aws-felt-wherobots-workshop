# CLAUDE.md — Workshop Build Plan

## What This Is
"From Satellite to Signal: Building a Geospatial Agentic AI Stack on AWS"
90-minute hands-on workshop. Felt × Wherobots × AWS.

### Three deliverables
1. **GitHub repo** — working code, skills, .md instructions
2. **Step-by-step workshop document** — AWS Workshop Studio format
3. **Presentation** — later

## People
- **Jaime** (Felt) — Owns workshop deliverable
- **Pranav Toggi** (Wherobots) — Created Iceberg tables, Wherobots MCP expert
- **Damion Harrylal** (AWS SA) — Workshop format owner, AWS credits/infra
- **Sarab** (AWS) — Infrastructure, shared geospatial-change-detection-agent-gis repo
- **Rajesh** (AWS) — Infrastructure

## Architecture Vision
The agent model is **skills + .md files + code execution engine** — NOT wrapped @tool functions.
The Strands agent reads skill docs, generates Python code, and executes it.

```
User prompt: "Show wildfire risk for Austin buildings"
                    ↓
           Strands Agent (Bedrock Claude)
           reads: skills/*.md
                    ↓
           Generates Python code that:
           1. Queries Aurora PostGIS (via psycopg2)
           2. Calls felt-python to create map + upload + style
                    ↓
           Code execution engine runs it
                    ↓
           Returns Felt map URL
```

## Part 1 — Agentic Data Engineering (Wherobots MCP)

### What Wherobots MCP Actually Is
- **Hosted HTTP MCP server** at `https://api.cloud.wherobots.com/mcp/`
- NOT a pip package — it's a remote server
- Auth: API key passed in config
- Capabilities: catalog exploration, spatial SQL generation, query execution
- Works with VS Code extension or manual MCP config
- Config for Claude Desktop / Strands:
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

### Wherobots Table Paths (Pranav created these)
| Dataset | WB Table Path |
|---------|--------------|
| NOAA Severe Weather | `org_catalog.noaa_swdi` |
| MODIS Flood | `org_catalog.modis` |
| USFS Wildfire | `org_catalog.wildfire_risk` |
| Overture Buildings | `wherobots_open_data.overture_maps_foundation` |

### Medallion Pipeline
- **Bronze**: Raw data from Wherobots catalog tables (as-is from S3)
- **Silver**: Cleaned, standardized to COG + GeoParquet, spatial joins
- **Gold**: Per-asset risk scores + score_explanation, written to Aurora PostgreSQL

### JDBC Export to Aurora
Sedona can write directly via JDBC:
```sql
CREATE TABLE aurora_export USING jdbc OPTIONS (
  url 'jdbc:postgresql://{host}:5432/{db}',
  dbtable 'public.building_risk',
  user '{user}', password '{password}',
  driver 'org.postgresql.Driver'
) AS SELECT * FROM gold_building_risk;
```

## Part 2 — Map Builder AI Agent (Aurora + Felt MCP)

### Felt Source Connection (SDK)
Use `felt-python` `create_source()` to register Aurora as a live data source:
```python
from felt_python import create_source
source = create_source(
    name="Workshop Aurora PostGIS",
    connection={
        "type": "postgresql",
        "host": "dpg-cs6np65umphs73e7tkog-a.oregon-postgres.render.com",
        "database": "sales_engineers",
        "user": "sales_engineers_user",
        "password": "...",
        "schema": "public"
    }
)
# source["id"] → use for add_source_layer
```

Then add layers with SQL spatial filtering:
```python
from felt_python import add_source_layer
response = add_source_layer(
    map_id="...",
    source_layer_params={
        "from": "sql",
        "source_id": source["id"],
        "query": """
            SELECT asset_id, ST_Transform(geometry, 4326) as geometry,
                   risk_score, risk_category, dominant_hazard
            FROM building_risk
            WHERE risk_category = 'critical'
        """
    }
)
```

### Felt Skills (from aws-workshop-felt-skills repo)
Jaime's repo: https://github.com/jaime-blip/aws-workshop-felt-skills
Contains:
- `skills/felt-map-maker/SKILL.md` — Comprehensive felt-python + FSL skill doc
- `skills/felt-map-maker/scripts/skill.py` — Helper functions
- `skills/felt-js-sdk/` — JS SDK skill (not needed for this workshop)
- `evals/` — Evaluation framework for skill testing
- Multiple scenarios with reference implementations

### Agent Architecture
Strands agent with:
1. **Skill .md files** that teach it how to use felt-python and PostGIS
2. **Code execution** — agent writes and runs Python
3. **No hardcoded @tool wrappers** — agent reads docs and generates code

### Output
Agent takes: `"Show wildfire risk for Austin buildings"`
Agent does:
1. Reads skill docs (PostGIS querying, Felt map creation, FSL styling)
2. Generates Python that queries Aurora PostGIS
3. Creates Felt map, adds source layer with SQL filter
4. Applies FSL categorical styling (risk colors)
5. Returns shareable Felt map URL

## Gold Layer Output Schema
| Field | Description |
|-------|-------------|
| asset_id | Unique building identifier |
| geometry | PostGIS geometry (Point/Polygon, SRID 4326) |
| event_window_start/end | Temporal bounds for event observation |
| baseline_window_start/end | Temporal bounds for baseline comparison |
| wildfire_factor | Normalized wildfire burn probability (0-1) |
| flood_factor | Normalized flood extent/frequency (0-1) |
| severe_weather_factor | Normalized severe weather density (0-1) |
| risk_score | Composite weighted score |
| score_explanation | JSON detailing contributing factors |

## Credentials
```
FELT_API_TOKEN=felt_pat_IBAiwDtnIUN6sNCBOssJXG5DJWXDun7aaODueyKnYlk
WHEROBOTS_API_KEY=19e484ca-8088-4b22-b920-f0600a64dc26
AURORA_DSN=postgresql://sales_engineers_user:ZwIZ5dUqaAwfUlgirLoStAHzIMrY0f99@dpg-cs6np65umphs73e7tkog-a.oregon-postgres.render.com/sales_engineers
```

## Existing Resources
- **Jaime's felt-skills repo**: https://github.com/jaime-blip/aws-workshop-felt-skills
- **Sarab's change detection agent**: `geospatial-change-detection-agent-gis-main.zip` (Slack — need Jaime to download)
- **Wherobots MCP**: https://api.cloud.wherobots.com/mcp/ (HTTP server)
- **Wherobots MCP docs**: https://docs.wherobots.com/develop/mcp/mcp-server-setup.md
- **AWS Workshop format example**: https://catalog.us-east-1.prod.workshops.aws/workshops/7f1e393b-c2fd-4cc4-b4f9-8e75db2326eb
- **Felt OpenAPI**: https://felt.com/api/v2/openapi.json

## TODO
- [ ] Get Sarab's zip from Slack (need auth'd download)
- [ ] Test Wherobots MCP connection with our API key
- [ ] Test queries against org_catalog tables (noaa_swdi, modis, wildfire_risk)
- [ ] Test Aurora PostgreSQL connection (Render instance)
- [ ] Test Felt create_source with PostgreSQL params
- [ ] Build Part 1 notebooks using real Wherobots MCP
- [ ] Build Part 2 agent with skills + code execution
- [ ] Write step-by-step workshop document
- [ ] Create architecture diagram
