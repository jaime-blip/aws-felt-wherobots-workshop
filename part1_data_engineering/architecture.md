# Architecture — Geospatial Risk Intelligence Pipeline

> **Pipeline**: Raw (S3) → Bronze (Iceberg) → Silver (Iceberg) → Gold (Iceberg → Aurora PostgreSQL) → Felt Maps
>
> **Runtime**: [Wherobots Cloud](https://wherobots.com/) with Apache Sedona
>
> **Target Industries**: Insurance, Commercial Real Estate, Capital Markets, Energy & Utilities

---

## Pipeline Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATION LAYER                                │
│  Wherobots MCP (data eng)    Strands Agent (maps)    Felt MCP (viz)     │
│  api.cloud.wherobots.com     Bedrock Claude           felt.com/mcp      │
└───────┬────────────────────────────┬──────────────────────┬─────────────┘
        │                            │                      │
        ▼                            │                      │
┌──────────────────┐                 │                      │
│  RAW DATA (S3)   │                 │                      │
│  - NOAA SWDI     │                 │                      │
│  - MODIS Flood   │                 │                      │
│  - USFS Wildfire │                 │                      │
│  - Overture Bld  │                 │                      │
└───────┬──────────┘                 │                      │
        │ bronze-to-silver.ipynb     │                      │
        │ Zonal Stats, KNN          │                      │
        │ Spatial Joins              │                      │
        ▼                            │                      │
┌──────────────────┐                 │                      │
│  SILVER (Iceberg)│                 │                      │
│  - Wildfire Exp  │                 │                      │
│  - Flood Exp     │                 │                      │
│  - Weather Dens  │                 │                      │
│  - Asset Enrich  │                 │                      │
└───────┬──────────┘                 │                      │
        │ silver-to-gold.ipynb       │                      │
        │ Normalization              │                      │
        │ Industry Weighting         │                      │
        ▼                            │                      │
┌──────────────────┐                 │                      │
│  GOLD (Iceberg)  │   JDBC          │                      │
│  358K buildings  ├────────────────▶│                      │
│  x 4 verticals  │                 │                      │
└──────────────────┘   ┌─────────────▼────────────┐        │
                       │ AURORA POSTGRESQL         │        │
                       │ workshop schema           │ Source │
                       │ PostGIS + Indexes         ├────────▶
                       │                           │        │
                       │ Agent queries via         │  ┌─────▼───────────┐
                       │ psycopg2 (python_repl)    │  │  FELT MAPS       │
                       └───────────────────────────┘  │  - Risk by tier   │
                                                      │  - Industry views  │
                                                      │  - Spatial queries │
                                                      └──────────────────┘
```

**Note:** There is no Aurora MCP server. The Strands agent connects to Aurora directly via `psycopg2` through the `python_repl` tool, guided by the `aurora-postgis` skill. Felt connects to Aurora as a registered data source for live source layers.

---

## Notebook Sequence

| Step | Notebook | What it does |
|------|----------|--------------|
| 1 | `bronze-to-silver.ipynb` | Spatial joins, zonal statistics (raster → vector), KNN event proximity → Silver Iceberg |
| 2 | `silver-to-gold.ipynb` | Industry-specific normalization, weighted scoring, risk tiers → Gold Iceberg + JDBC to Aurora |

> The raw-to-bronze step is handled by Wherobots' catalog — Bronze data lives in `org_catalog` and `wherobots_open_data` as pre-registered Iceberg tables.

---

## Data Sources

| Dataset | Source | Type | Catalog Table |
|---------|--------|------|---------------|
| NOAA SWDI — Hail | [AWS Open Data](https://registry.opendata.aws/noaa-swdi/) | Vector | `org_catalog.noaa_swdi.hail` |
| NOAA SWDI — Mesocyclone | AWS Open Data | Vector | `org_catalog.noaa_swdi.structure` |
| NOAA SWDI — TVS | AWS Open Data | Vector | `org_catalog.noaa_swdi.tvs` |
| MODIS MCDWD Flood NRT | [NASA LANCE](https://nrt3.modaps.eosdis.nasa.gov/) | Raster (GeoTIFF) | `org_catalog.modis.MCDWD_L3_F3_NRT` |
| USFS Burn Probability | [wildfirerisk.org](https://wildfirerisk.org/) | Raster (COG) | `org_catalog.wildfire_risk.burn_probability_conus` |
| USFS Conditional Flame Length | wildfirerisk.org | Raster (COG) | `org_catalog.wildfire_risk.conditional_flame_length_conus` |
| Overture Buildings | [Wherobots Open Data](https://docs.wherobots.com/) | Vector (GeoParquet) | `wherobots_open_data.overture_maps_foundation.buildings_building` |

---

## Layer Details

### Silver — Spatial Analytics

The heavy compute layer where Wherobots/Sedona performs spatial joins, zonal statistics, KNN, and buffered aggregations to conflate hazard signals onto building footprints.

| Silver Table | Operation | Hazard Source |
|---|---|---|
| `asset_wildfire_exposure` | Zonal statistics (raster → vector) | USFS burn probability + flame length |
| `asset_flood_exposure` | Zonal statistics + temporal aggregation | MODIS flood NRT |
| `asset_weather_density` | KNN spatial join (k=10, 25km radius) | NOAA SWDI hail / structure / TVS |
| `asset_enriched` | LEFT JOIN of all above onto buildings | All hazards unified |

Each table is an independently materialized Iceberg table — reprocessing one hazard does not require recomputing others.

### Gold — Industry-Specific Scoring

All Gold tables start from `asset_enriched` and apply the same framework:

1. **Normalize** raw hazard metrics to [0, 1] via min-max scaling
2. **Weight** the three factors per industry
3. **Classify** into risk tiers (High ≥ 0.60, Elevated ≥ 0.40, Moderate ≥ 0.20, Low < 0.20)
4. **Derive** industry-specific metrics

| Gold Table | Aurora Table | Industry | Weights (wf / fl / sw) | Key Derived Metrics |
|---|---|---|---|---|
| `insurance_exposure` | `workshop.insurance_exposure` | Insurance | 0.40 / 0.40 / 0.20 | exposure_delta, triage_priority, estimated_loss_band |
| `cre_risk` | `workshop.cre_risk` | Commercial Real Estate | 0.30 / 0.35 / 0.35 | acquisition_screen_flag, environmental_risk_index, hazard_proximity_m |
| `capmarkets_signals` | `workshop.capmarkets_signals` | Capital Markets | 0.20 / 0.30 / 0.50 | disruption_probability, supply_chain_vulnerability, event_signal_strength |
| `energy_infra_risk` | `workshop.energy_infra_risk` | Energy & Utilities | 0.40 / 0.20 / 0.40 | outage_probability, vegetation_encroachment_risk, weather_impact_frequency |

> For full column-level detail and business logic, see [data_dictionary.md](data_dictionary.md).

---

## Output Destination

Gold tables are exported to Aurora PostgreSQL via JDBC:

| Destination | Schema | Format |
|---|---|---|
| Aurora PostgreSQL | `workshop.*` | PostGIS (GEOMETRY + indexes) via JDBC |

> DDL reference: [aurora_schema.sql](aurora_schema.sql) (note: uses `gold` schema and older column names — Aurora actual schema is `workshop` with names as listed in the Gold table above)

---

## How the Agent Queries Aurora

The Part 2 MapBuilder agent does **not** use an Aurora MCP server. Instead:

1. The `aurora-postgis` **skill** (.md file) teaches the agent PostGIS query patterns
2. The agent generates Python code using `psycopg2` to query Aurora
3. The code runs in `python_repl` (Strands tool)
4. Results flow to `felt_python` for map creation

This "skills + code execution" approach is more flexible than an MCP — the agent can compose arbitrary SQL, spatial joins, and multi-step workflows in a single Python script.

---

## Felt Integration

Maps are created two ways:

| Method | Used by | How it connects to Aurora |
|---|---|---|
| **felt-python SDK** (via Strands agent) | Developer workflow | `add_source_layer()` with SQL query against Aurora data source |
| **Felt MCP** (`https://felt.com/mcp`) | Business user / conversational | `create_layer_from_data_source` tool queries Aurora directly |

Both use Felt's **source layer** feature — the map connects live to Aurora, so data updates flow through automatically.

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Geographic scope | San Diego, CA | Wildfire + flood + severe weather overlap; compact for workshop |
| Asset type | Buildings (Overture) | Available via Wherobots Open Data; 358K in San Diego |
| Aurora schema | `workshop` | Isolated from other data; clean for CloudFormation seeding |
| No Aurora MCP | Agent uses psycopg2 via skills | Simpler setup; skills + code execution is more flexible |
| Gold persistence | Iceberg + Aurora | Iceberg for reprocessing, Aurora for serving and Felt connectivity |
| Normalization | Min-max (0–1 range) | Intuitive for workshop; AOI-relative (not comparable across regions) |
| Risk tiers | High / Elevated / Moderate / Low | 4 tiers, no "Critical" — matches actual data distribution |
| Refresh cadence | Full refresh (truncate-and-load) | Suitable for workshop; upsert pattern for production |
