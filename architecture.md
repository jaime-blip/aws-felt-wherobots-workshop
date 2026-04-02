# Architecture — Geospatial Agentic AI Stack

> **An end-to-end workflow that takes raw satellite imagery and weather data through agentic data engineering, risk scoring, and into interactive map dashboards — all driven by natural language.**
>
> **Part 1 — Data Engineering:** Developer + [Wherobots MCP](https://api.cloud.wherobots.com/mcp/) → Medallion pipeline (Bronze → Silver → Gold) → Aurora PostgreSQL
>
> **Part 2 — Map Agent:** [Strands Agent](https://github.com/strands-agents/sdk-python) (Bedrock Claude) + [Felt MCP](https://felt.com/mcp) → Interactive maps from natural language
>
> **Target Industries**: Insurance, Commercial Real Estate, Capital Markets, Energy & Utilities

---

## Architecture Overview

The system has two parts — one for data engineering, one for end-user exploration:

```
╔══════════════════════════════════════════════════════════════════════════╗
║  PART 1 — DATA ENGINEERING AGENT                                        ║
║  Persona: Data engineer / analyst in Claude Code or Kiro                ║
║                                                                         ║
║  ┌─────────────────┐     ┌──────────────────────────────────────┐      ║
║  │ Developer        │     │ Wherobots MCP                        │      ║
║  │ (Claude Code /   │────▶│ https://api.cloud.wherobots.com/mcp/ │      ║
║  │  Kiro / VS Code) │     │ + wherobots-pipeline skill           │      ║
║  └─────────────────┘     └───────────────┬──────────────────────┘      ║
║                                          │                              ║
║    "Generate a notebook that scores      │  Discovers catalogs,         ║
║     San Diego buildings for wildfire,    │  generates Sedona SQL,       ║
║     flood, and weather risk"             │  executes on Spark           ║
║                                          ▼                              ║
║  ┌──────────┐   ┌──────────┐   ┌──────────┐   JDBC   ┌──────────────┐ ║
║  │ RAW (S3) │──▶│ SILVER   │──▶│ GOLD     │─────────▶│ AURORA       │ ║
║  │ NOAA     │   │ Zonal    │   │ Scoring  │          │ PostgreSQL   │ ║
║  │ MODIS    │   │ Stats    │   │ Weighting│          │ workshop.*   │ ║
║  │ USFS     │   │ KNN Join │   │ Tiers    │          │ 358K x 4    │ ║
║  │ Overture │   │          │   │          │          │              │ ║
║  └──────────┘   └──────────┘   └──────────┘          └──────┬───────┘ ║
╚══════════════════════════════════════════════════════════════╪═════════╝
                                                               │
                           Aurora is the handoff point         │
                           between the two parts               │
                                                               │
╔══════════════════════════════════════════════════════════════╪═════════╗
║  PART 2 — END-USER MAP AGENT                                │         ║
║  Persona: Analyst / business user asking questions           │         ║
║                                                              │         ║
║  ┌─────────────────┐     ┌──────────────────────────────┐   │         ║
║  │ User prompt:     │     │ Strands Agent                │   │         ║
║  │ "Show buildings  │────▶│ (Amazon Bedrock Claude)      │   │         ║
║  │  with high       │     │                              │   │         ║
║  │  wildfire risk    │     │ Skills:                      │   │         ║
║  │  near Poway"     │     │  - aurora-postgis            │   │         ║
║  └─────────────────┘     │  - felt-mapping              │   │         ║
║                           └──────────┬───────────────────┘   │         ║
║                                      │ generates Python      │         ║
║                                      ▼                       │         ║
║                           ┌──────────────────────┐           │         ║
║                           │ python_repl           │           │         ║
║                           │                       │           │         ║
║                           │ psycopg2 → Aurora ◀───────────────┘         ║
║                           │ felt_python → Felt MCP                      ║
║                           │ FSL → Styling                               ║
║                           └──────────┬───────────┘                      ║
║                                      │                                  ║
║                                      ▼                                  ║
║                           ┌──────────────────────┐                      ║
║                           │ Felt Map              │                      ║
║                           │ https://felt.com/mcp  │                      ║
║                           │ - Interactive layers   │                      ║
║                           │ - Live Aurora source   │                      ║
║                           │ - Shareable URL        │                      ║
║                           └──────────────────────┘                      ║
╚═════════════════════════════════════════════════════════════════════════╝
```

### Why two parts?

| | Part 1: Data Engineering | Part 2: Map Agent |
|---|---|---|
| **Persona** | Data engineer in an IDE | Analyst asking questions |
| **Interface** | Claude Code / Kiro + Wherobots MCP | Strands Agent CLI or Felt MCP chat |
| **Intelligence** | MCP-guided notebook generation | Skills + code execution |
| **Runs when** | Pipeline build time (once or on schedule) | Ad-hoc, interactive, on demand |
| **Output** | Scored tables in Aurora | Interactive Felt maps |
| **MCP servers** | Wherobots | Felt |

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

## How the End-User Agent Works (Part 2)

The Strands MapBuilder agent combines **skills + code execution + Felt MCP**:

1. **Skills** (`.md` files) teach the agent PostGIS patterns and Felt styling
2. The agent generates Python using `psycopg2` to query Aurora and `felt_python` to create maps
3. Code runs in `python_repl` (Strands tool)
4. **Felt MCP** (`https://felt.com/mcp`) provides additional tools: `create_layer_from_data_source`, `update_layer_style`, `get_tabular_data_from_data_source`

There is no Aurora MCP — the agent reaches Aurora two ways:
- **Direct SQL** via `psycopg2` (for complex PostGIS queries like `ST_DWithin`, spatial joins)
- **Felt source layers** via Felt MCP or `felt_python` SDK (Aurora is a registered data source in Felt — SQL queries run server-side)

Both produce **live source layers** — the map stays connected to Aurora, so data updates flow through automatically.

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Two-layer architecture | Wherobots MCP (data eng) + Strands/Felt MCP (maps) | Clean separation: data engineer builds pipeline, analyst explores maps |
| Geographic scope | San Diego, CA | Wildfire + flood + severe weather overlap; compact for workshop |
| Asset type | Buildings (Overture) | Available via Wherobots Open Data; 358K in San Diego |
| Aurora as handoff | `workshop` schema | Aurora bridges the two parts — pipeline writes, agent reads |
| No Aurora MCP | Agent uses psycopg2 + Felt source layers | Felt MCP already queries Aurora; adding a third MCP is redundant |
| Gold persistence | Iceberg + Aurora | Iceberg for reprocessing, Aurora for serving and Felt connectivity |
| Normalization | Min-max (0–1 range) | Intuitive for workshop; AOI-relative (not comparable across regions) |
| Risk tiers | High / Elevated / Moderate / Low | 4 tiers, no "Critical" — matches actual data distribution |
| Refresh cadence | Full refresh (truncate-and-load) | Suitable for workshop; upsert pattern for production |
