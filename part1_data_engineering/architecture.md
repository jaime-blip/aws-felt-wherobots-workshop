# Architecture — Geospatial Risk Intelligence Pipeline

> **Pipeline**: Raw (S3) → Bronze (Iceberg) → Silver (Iceberg) → Gold (Iceberg + GeoParquet → Aurora PostgreSQL) → Felt Maps
>
> **Runtime**: [Wherobots Cloud](https://wherobots.com/) with Apache Sedona
>
> **Target Industries**: Insurance, Commercial Real Estate, Capital Markets, Energy & Utilities

---

## Pipeline Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                       ORCHESTRATION LAYER                                │
│           Amazon Strands Agent + MCP Servers                             │
│  (Wherobots MCP)          (Aurora MCP)          (Felt MCP)               │
└───────┬────────────────────────┬──────────────────────┬──────────────────┘
        │                        │                      │
        ▼                        │                      │
┌──────────────────┐             │                      │
│  RAW DATA (S3)   │             │                      │
│  - NOAA SWDI     │             │                      │
│  - MODIS Flood   │             │                      │
│  - USFS Wildfire │             │                      │
│  - Overture Bld  │             │                      │
└───────┬──────────┘             │                      │
        │ raw-to-bronze.ipynb    │                      │
        ▼                        │                      │
┌──────────────────┐             │                      │
│  BRONZE (Iceberg)│             │                      │
│  Schema + Dedup  │             │                      │
│  Time Travel     │             │                      │
└───────┬──────────┘             │                      │
        │ bronze-to-silver.ipynb │                      │
        │ Zonal Stats, KNN      │                      │
        │ Spatial Joins          │                      │
        ▼                        │                      │
┌──────────────────┐             │                      │
│  SILVER (Iceberg)│             │                      │
│  - Wildfire Exp  │             │                      │
│  - Flood Exp     │             │                      │
│  - Weather Dens  │             │                      │
│  - Asset Enrich  │             │                      │
└───────┬──────────┘             │                      │
        │ silver-to-gold.ipynb   │                      │
        │ Normalization          │                      │
        │ Industry Weighting     │                      │
        ▼                        │                      │
┌──────────────────┐             │                      │
│  GOLD (Iceberg   │   JDBC     │                      │
│  + GeoParquet)   ├────────────▶                      │
│  - Insurance     │             │                      │
│  - CRE           │   ┌────────▼──────────┐           │
│  - CapMarkets    │   │ AURORA POSTGRESQL  │  Publish  │
│  - Energy        │   │ (Serving Layer)    ├───────────▶
│  - Scoring Cfg   │   │ PostGIS + Indexes  │           │
└──────────────────┘   └───────────────────┘  ┌────────▼────────┐
                                              │  FELT MAPS       │
                                              │  - Insurance CAT  │
                                              │  - CRE Screening  │
                                              │  - CapMkt Signals  │
                                              │  - Energy Grid     │
                                              └──────────────────┘
```

---

## Notebook Sequence

| Step | Notebook | What it does |
|------|----------|--------------|
| 1 | `raw-to-bronze.ipynb` | Ingest raw CSV / GeoTIFF / raster from S3 and Wherobots Open Data into Bronze Iceberg tables |
| 2 | `bronze-to-silver.ipynb` | Spatial joins, zonal statistics (raster → vector), KNN event proximity → Silver Iceberg |
| 3 | `silver-to-gold.ipynb` | Industry-specific normalization, weighted scoring, risk tiers → Gold Iceberg + GeoParquet |

---

## Data Sources

| Dataset | Source | Type | Catalog Table |
|---------|--------|------|---------------|
| NOAA SWDI — Hail | [AWS Open Data](https://registry.opendata.aws/noaa-swdi/) | Vector (CSV) | `org_catalog.noaa_swdi.hail` |
| NOAA SWDI — Mesocyclone Structures | AWS Open Data | Vector (CSV) | `org_catalog.noaa_swdi.structure` |
| NOAA SWDI — TVS | AWS Open Data | Vector (CSV) | `org_catalog.noaa_swdi.tvs` |
| NOAA SWDI — Warnings | AWS Open Data | Vector (CSV) | `org_catalog.noaa_swdi.warn` |
| MODIS MCDWD Flood NRT | [NASA LANCE](https://nrt3.modaps.eosdis.nasa.gov/) | Raster (GeoTIFF) | `org_catalog.modis.MCDWD_L3_F3_NRT` |
| USFS Burn Probability | [wildfirerisk.org](https://wildfirerisk.org/) | Raster (COG) | `org_catalog.wildfire_risk.burn_probability_conus` |
| USFS Conditional Flame Length | wildfirerisk.org | Raster (COG) | `org_catalog.wildfire_risk.conditional_flame_length_conus` |
| Overture Buildings | [Wherobots Open Data](https://docs.wherobots.com/) | Vector (GeoParquet) | `wherobots_open_data.overture_maps_foundation.buildings_building` |

---

## Layer Details

### Bronze — Cataloged Raw

Raw source data converted to **Apache Iceberg tables** with schema enforcement. Still close-to-raw, but queryable via SQL and supporting time travel for before/after analysis.

- Schema enforcement (cast types, validate geometries)
- Deduplication on natural keys
- Append-only ingestion — no updates to historical records
- Iceberg snapshots enable time travel for baseline vs. event window queries

### Silver — Spatial Analytics

The heavy compute layer where Wherobots/Sedona performs spatial joins, zonal statistics, KNN, and buffered aggregations to conflate hazard signals onto building footprints.

| Silver Table | Operation | Hazard Source |
|---|---|---|
| `asset_wildfire_exposure` | Zonal statistics (raster → vector) | USFS burn probability + flame length |
| `asset_flood_exposure` | Zonal statistics + temporal aggregation | MODIS flood NRT |
| `asset_weather_density` | KNN spatial join (vector → vector) | NOAA SWDI hail / structure / TVS |
| `asset_enriched` | LEFT JOIN of all above onto buildings | All hazards unified |

Each table is an independently materialized Iceberg table — reprocessing one hazard does not require recomputing others.

### Gold — Industry-Specific Scoring

All Gold tables start from `silver.asset_enriched` and apply the same framework:

1. **Normalize** raw hazard metrics to [0, 1] via min-max scaling
2. **Weight** the three factors per industry
3. **Classify** into risk tiers (Critical / High / Elevated / Moderate / Low)
4. **Add** industry-specific derived metrics

| Gold Table | Industry | Weights (wf / fl / sw) | Key Derived Metrics |
|---|---|---|---|
| `insurance_exposure` | Insurance | 0.40 / 0.40 / 0.20 | exposure_delta, triage_priority, relative_risk_band |
| `cre_risk` | Commercial Real Estate | 0.30 / 0.35 / 0.35 | acquisition_screen_flag, exposure_magnitude_index |
| `capital_markets_signals` | Capital Markets | 0.20 / 0.30 / 0.50 | disruption_signal, supply_chain_vulnerability |
| `energy_asset_risk` | Energy & Utilities | 0.40 / 0.20 / 0.40 | outage_probability, wildfire_ignition_risk |

> For full column-level detail and business logic, see [data_dictionary.md](data_dictionary.md).

---

## Output Destinations

Each Gold table is written to three destinations:

| Destination | Format | Location |
|---|---|---|
| Wherobots Iceberg | Apache Iceberg | `org_catalog.gold.<table_name>` |
| S3 GeoParquet | GeoParquet | `s3://.../data/shared/gold/<table_name>` |
| Aurora PostgreSQL | PostGIS (via JDBC) | `gold.<table_name>` |

> Aurora DDL is in [aurora_schema.sql](aurora_schema.sql).

---

## Felt Map Configurations

| Felt Map | Gold Source | Layer Style | Popup Fields |
|---|---|---|---|
| Insurance CAT Triage | `insurance_exposure` | Color ramp by `risk_tier` (green → red) | risk_score, exposure_delta, triage_priority, estimated_loss_band |
| CRE Acquisition Screening | `cre_risk` | Bivariate: risk_score × assessed_value | risk_score, acquisition_screen_flag, environmental_risk_index |
| CapMarkets Disruption Monitor | `capmarkets_signals` | Size by disruption_probability, color by signal_strength | disruption_probability, supply_chain_vulnerability |
| Energy Grid Vulnerability | `energy_infra_risk` | Color ramp by `risk_tier`, outline by outage_probability | outage_probability, vegetation_encroachment_risk |

---

## Aurora → Felt Publishing Flow

```
Aurora PostgreSQL (Gold tables)
    │
    ▼
[Felt MCP Server / Felt API]
    ├── Create/update layer per Gold table
    ├── Apply industry-specific map style
    ├── Configure popups with score breakdown
    └── Publish shareable map link
```

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Geographic scope | San Diego, CA (AOI) | Wildfire + flood + severe weather overlap; compact enough for workshop |
| Asset type | Buildings (Overture) | Available via Wherobots Open Data; parcels as future extension |
| Temporal windows | Configurable via notebook params | Default: baseline = 1 yr prior, event = 30-day window |
| Gold persistence | Iceberg + GeoParquet + Aurora | Iceberg for reprocessing, GeoParquet for portability, Aurora for serving |
| Normalization | Min-max (0–1 range) | Intuitive for workshop; AOI-relative (not comparable across regions); percentile rank for production |
| Refresh cadence | Full refresh (truncate-and-load) | Suitable for workshop; upsert pattern for production |
| Scoring config | Iceberg table + replicated to Aurora | Parameterizable weights; auditable via version column |
