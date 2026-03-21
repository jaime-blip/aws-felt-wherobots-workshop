# CLAUDE.md — Workshop Build Plan

## What This Is
"From Satellite to Signal: Building a Geospatial Agentic AI Stack on AWS"
A 90-minute hands-on workshop presented by **Felt**, **Wherobots**, and **AWS**.
Three deliverables: **GitHub repo** (code), **step-by-step workshop doc**, **presentation** (later).

## People
- **Jaime** (Felt) — Partnerships, owns the workshop deliverable
- **Pranav Toggi** (Wherobots) — Wherobots MCP, data engineering, created Iceberg tables
- **Damion Harrylal** (AWS SA) — Workshop format, AWS credits, Aurora, CloudFormation
- **Sarab** (AWS) — Infrastructure provisioning
- **Rajesh** (AWS) — Infrastructure provisioning

## Key Decisions
- **Aurora = Amazon Aurora PostgreSQL 17 with PostGIS** (NOT the Microsoft weather model)
- **Wherobots MCP** = their actual MCP server (not just the Python SDK)
- **Felt MCP** = Felt's MCP server for map creation
- **Strands Agents SDK** = AWS agent framework (NOT LangChain)
- **Kiro IDE** = AWS AI IDE (mentioned in abstract, TBD if we integrate)
- Format: AWS Workshop Studio style (like https://catalog.us-east-1.prod.workshops.aws/workshops/7f1e393b-c2fd-4cc4-b4f9-8e75db2326eb)
- No AWS account required for attendees — all infrastructure pre-provisioned via CloudFormation

## Wherobots Table Paths (from Pranav, Notion doc)
- NOAA SWDI: `org_catalog.noaa_swdi`
- MODIS flood: `org_catalog.modis`
- USFS wildfire: `org_catalog.wildfire_risk`
- Buildings: `wherobots_open_data.overture_maps_foundation`

## Architecture
```
Bronze (raw S3)  →  Silver (COG + GeoParquet)  →  Gold (Aurora PostgreSQL)
     ↑                      ↑                           ↓
  MODIS flood         Cleaned/joined              Scored buildings
  NOAA storms         Normalized 0-1              + risk categories
  USFS wildfire       Spatial joins               + score_explanation
  Overture bldgs
                                                        ↓
                                              Strands Agent (Bedrock)
                                                   ↙        ↘
                                            Aurora PostGIS   Felt MCP
                                            (spatial query)  (map publish)
                                                        ↓
                                                   Felt Map URL
```

## Workshop Flow (90 minutes)
| Time | Module | Details |
|------|--------|---------|
| 10m | Context + Setup | Frame the question; intro architecture; before/after concept |
| 20m | Bronze → Silver | Load raw inputs; standardize to COG + GeoParquet |
| 20m | Silver → Gold | Wherobots: zonal stats / spatial joins → per-asset features → Aurora |
| 15m | Scoring | Normalize factors; compute weighted score; persist to Aurora |
| 20m | Publish + Visualize | Felt layers (baseline vs event); style by score; share map |
| 5m | Wrap + Extensions | Productionize, add more hazards/models |

## Part 1 — Agentic Data Engineering (Wherobots MCP)
- Full AI development experience — agent drives the pipeline via MCP
- Load MODIS + NOAA + USFS + Overture from Wherobots catalog (real Iceberg tables!)
- Medallion: bronze (raw) → silver (clean/normalize/join) → gold (scored)
- JDBC export gold → Aurora PostgreSQL

### What's REAL vs STUBBED
- ✅ REAL: Wherobots Iceberg tables exist (Pranav created them)
- ✅ REAL: Wherobots API key works
- ✅ REAL: Aurora PostgreSQL connection works (Render-hosted for now)
- ❓ TODO: Find/confirm Wherobots MCP server package name & config
- ❓ TODO: Test actual queries against org_catalog tables
- ❓ TODO: Sarab's geospatial-change-detection-agent-gis repo (shared as zip in Slack)

## Part 2 — Map Builder AI Agent (Aurora + Felt MCP)
- Set up Felt MCP tools and skills
- Add Aurora as a source to Felt, spatial filtering with PostGIS
- Strands agent: "Show wildfire risk for Austin buildings" → queries Aurora → Felt map URL

### What's REAL vs STUBBED
- ✅ REAL: Felt API token works
- ✅ REAL: felt-python SDK works
- ❓ TODO: Use actual Felt MCP server (not just @tool wrappers)
- ❓ TODO: "Add Aurora as a source to Felt" — is this Felt's database connector? Or just API upload?
- ❓ TODO: Strands agent calling Felt MCP server (not felt-python wrappers)

## Output Schema (Gold Layer)
| Field | Description |
|-------|-------------|
| asset_id | Unique building identifier |
| geometry | PostGIS Point/Polygon |
| event_window_start/end | Temporal bounds for event observation |
| baseline_window_start/end | Temporal bounds for baseline comparison |
| wildfire_factor | Normalized wildfire burn probability (0-1) |
| flood_factor | Normalized flood extent/frequency (0-1) |
| severe_weather_factor | Normalized severe weather density (0-1) |
| risk_score | Composite weighted score |
| score_explanation | JSON detailing contributing factors |

## Credentials
```
# .env (DO NOT COMMIT)
FELT_API_TOKEN=felt_pat_IBAiwDtnIUN6sNCBOssJXG5DJWXDun7aaODueyKnYlk
WHEROBOTS_API_KEY=19e484ca-8088-4b22-b920-f0600a64dc26
AURORA_DSN=postgresql://sales_engineers_user:ZwIZ5dUqaAwfUlgirLoStAHzIMrY0f99@dpg-cs6np65umphs73e7tkog-a.oregon-postgres.render.com/sales_engineers
```

## Existing Resources
- Jaime's felt-skills repo: https://github.com/jaime-blip/aws-workshop-felt-skills
- Sarab's change detection agent: geospatial-change-detection-agent-gis-main.zip (in Slack)
- Wherobots MCP server: TBD (need to confirm with Pranav)
- Felt MCP server: https://github.com/feltlabs/felt-mcp (or similar)
- AWS Workshop Studio format example: https://catalog.us-east-1.prod.workshops.aws/workshops/7f1e393b-c2fd-4cc4-b4f9-8e75db2326eb

## Open Questions for Jaime
1. "Add Aurora as a source to Felt" — is this the database source connector in Felt UI, or programmatic via API?
2. Should the Strands agent use Felt MCP server directly, or wrap felt-python as @tool functions?
3. Do we want the workshop to use Kiro IDE (mentioned in abstract)?
4. Sarab's zip — should we base Part 1 on their existing agent code?
5. CloudFormation template — is AWS team building this, or do we need to provide specs?
