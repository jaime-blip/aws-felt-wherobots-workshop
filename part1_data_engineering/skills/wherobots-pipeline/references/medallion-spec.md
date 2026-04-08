# Medallion Architecture — Layer Contracts

This document defines what each layer in the medallion pipeline **must guarantee**.
Use these contracts when designing the pipeline (Phase 3) and when auditing generated notebooks.

---

## General Principles

1. **Each layer is independently materializable.** Reprocessing Silver does not require reprocessing Bronze.
2. **Each table is independently materializable.** Reprocessing one Silver enrichment table does not require reprocessing others.
3. **No circular dependencies.** Data flows strictly: Raw -> Bronze -> Silver -> Gold -> Output.
4. **Every table is an Apache Iceberg table** (except final output destinations like GeoParquet/JDBC).
5. **Geometry column is always named `geometry`.**
6. **All timestamps are UTC.**

---

## Bronze Layer — Cataloged Raw

### Purpose
Convert raw source data into queryable, schema-enforced Iceberg tables. Still close to raw — no
analytics or joins at this layer.

### Guarantees

| Guarantee | What It Means |
|-----------|--------------|
| **Schema enforcement** | Every column has an explicit type (no implicit STRING from CSV). Geometry columns are proper GEOMETRY type. |
| **Geometry validity** | All geometry columns contain valid geometries created via `ST_Point`, `ST_GeomFromText`, or raster functions. No raw WKT strings as STRING columns. |
| **CRS tagging** | All raster data has CRS set via `RS_SetSRID`. All vector data is in EPSG:4326. |
| **Deduplication** | If the source has natural keys, duplicates are removed. Document the dedup key. |
| **Provenance** | Each row can be traced to its source. Include `ingested_at` timestamp. |
| **Idempotency** | Running the Bronze notebook twice produces the same result (`createOrReplace`). |

### What Bronze Does NOT Do
- No spatial joins or analytics
- No filtering by AOI (Bronze contains the full source extent, or at minimum the broad region)
- No normalization or scoring
- No cross-source joins

### Table Naming Convention
```
org_catalog.<data_domain>.<source_dataset>
```
Examples:
- `org_catalog.noaa_swdi.hail`
- `org_catalog.wildfire_risk.burn_probability_conus`
- `org_catalog.modis.MCDWD_L3_F3_NRT`

### Required Metadata Columns

| Column | Type | Description |
|--------|------|-------------|
| `geometry` | GEOMETRY or RASTER | Spatial column (named `geometry` for vectors, `raster` for raster data) |
| `ingested_at` | TIMESTAMP | When the row was ingested |

---

## Silver Layer — Spatial Analytics

### Purpose
Perform spatial joins, zonal statistics, KNN proximity analysis, and buffer aggregations to
produce per-entity enrichment metrics. The heavy compute layer.

### Guarantees

| Guarantee | What It Means |
|-----------|--------------|
| **Per-entity granularity** | Every Silver table has exactly one row per entity (building, parcel, asset). Aggregation is complete — no duplicate entity rows. |
| **AOI-filtered** | Only entities within the declared AOI polygon appear. |
| **Temporally bounded** | All event/observation data is filtered to the declared temporal windows. Window boundaries are recorded in the table. |
| **NULL semantics** | Missing data is NULL, not 0 or -1. NULL means "no data available", not "no risk". |
| **Coverage flags** | The unified enriched table includes boolean `has_<source>_data` flags to distinguish "no data" from "no risk". |
| **Independent enrichments** | Each hazard/signal source has its own Silver table. Reprocessing one does not require reprocessing others. |
| **Unified conflation** | The final Silver output (`asset_enriched`) LEFT JOINs all enrichment tables onto the entity base. |

### What Silver Does NOT Do
- No normalization to [0, 1] (that's Gold)
- No industry-specific weighting (that's Gold)
- No risk tier classification (that's Gold)
- No derived business metrics (that's Gold)

### Table Naming Convention
```
org_catalog.silver.asset_<source>_<operation>
org_catalog.silver.asset_enriched           # Always the final unified table
```
Examples:
- `org_catalog.silver.asset_wildfire_exposure`
- `org_catalog.silver.asset_flood_exposure`
- `org_catalog.silver.asset_weather_density`
- `org_catalog.silver.asset_enriched`

### Spatial Operation Selection Guide

Choose the correct spatial operation based on the source data type and the question being asked:

| Source Type | Question | Operation | Sedona Function |
|-------------|----------|-----------|----------------|
| Raster | "What is the value at this location?" | Zonal Statistics | `RS_ZonalStats(raster, geometry, 'mean')` |
| Raster | "Does this location intersect a hazard zone?" | Raster-Vector Filter | `RS_Intersects(raster, geometry)` |
| Vector (events) | "How many events are near this location?" | KNN Spatial Join | `ST_KNN(a.geom, b.geom, k, true, radius)` |
| Vector (events) | "What is the nearest event?" | KNN (k=1) | `ST_KNN(a.geom, b.geom, 1, true, radius)` |
| Vector (polygons) | "Does this location fall within a zone?" | Spatial Join | `ST_Intersects(a.geometry, b.geometry)` |
| Vector (polygons) | "How much of the zone overlaps?" | Intersection Area | `ST_Area(ST_Intersection(a.geom, b.geom))` |

### Required Columns in `asset_enriched`

| Column | Type | Source |
|--------|------|--------|
| `asset_id` | STRING | Entity identifier from the base table |
| `geometry` | GEOMETRY | Entity geometry from the base table |
| `<entity_attributes>` | varies | Key attributes from the base table (e.g., height, num_floors, class) |
| `<hazard_metrics>` | DOUBLE / INT | Raw metric columns from each enrichment table |
| `has_<source>_data` | BOOLEAN | Coverage flag per enrichment source |
| `baseline_window_start` | STRING | Pipeline parameter |
| `baseline_window_end` | STRING | Pipeline parameter |
| `event_window_start` | STRING | Pipeline parameter |
| `event_window_end` | STRING | Pipeline parameter |

---

## Gold Layer — Industry-Specific Scoring

### Purpose
Apply the 4-step scoring framework (normalize, weight, classify, derive) to produce
industry-specific risk scores and derived business metrics.

### Guarantees

| Guarantee | What It Means |
|-----------|--------------|
| **Same entity count as Silver** | Every entity from `asset_enriched` appears in every Gold table. No rows dropped. |
| **Normalized factors** | All hazard factors are in [0, 1] range via min-max scaling. |
| **Weights sum to 1.0** | Per-industry weights for all factors sum to exactly 1.0. |
| **Risk score in [0, 1]** | The weighted composite score is bounded. |
| **Risk tier assigned** | Every row has a categorical risk tier based on the score. |
| **Score explanation** | Every row has a JSON column breaking down the score into its component factors and weights. |
| **AOI-relative** | Normalization min/max are computed from the current AOI. Scores are NOT comparable across different AOIs. |

### What Gold Does NOT Do
- No new spatial operations (all spatial work is done in Silver)
- No data ingestion (all data comes from `asset_enriched`)

### Table Naming Convention
```
org_catalog.gold.<industry_or_usecase>_<metric_type>
```
Examples:
- `org_catalog.gold.insurance_exposure`
- `org_catalog.gold.cre_risk`
- `org_catalog.gold.capmarkets_signals`
- `org_catalog.gold.energy_asset_risk`

### Required Columns in Every Gold Table

| Column | Type | Description |
|--------|------|-------------|
| `asset_id` | STRING | Entity identifier |
| `geometry` | GEOMETRY | Entity geometry |
| `<factor_1>` | DOUBLE | Normalized factor (0-1) |
| `<factor_2>` | DOUBLE | Normalized factor (0-1) |
| `<factor_N>` | DOUBLE | Normalized factor (0-1) |
| `risk_score` | DOUBLE | Weighted composite (0-1) |
| `risk_tier` | STRING | Categorical tier |
| `score_explanation` | STRING (JSON) | Factor weights and values |
| `<derived_metrics>` | varies | Industry-specific derived columns |

---

## Output Destinations

Each Gold table is written to **at least** one destination. Typical destinations:

| Destination | Format | When to Use |
|-------------|--------|-------------|
| Wherobots Iceberg | `org_catalog.gold.<table>` | Always — primary persistence for reprocessing and querying |
| S3 GeoParquet | `s3://<bucket>/gold/<table>` | When downstream consumers need file-based access |
| Aurora PostgreSQL | `workshop.<table>` via JDBC | When serving to web applications or map platforms |

### Write Order

Always write in this order:
1. Iceberg (primary — if this fails, stop)
2. GeoParquet (secondary — portable format)
3. JDBC (tertiary — serving layer, optional)

---

## Cross-Layer Validation Rules

After the full pipeline runs, these invariants must hold:

| Rule | Check |
|------|-------|
| Entity count preserved | `COUNT(*)` in `asset_enriched` = `COUNT(*)` in every Gold table |
| No NULL risk scores | `SELECT COUNT(*) FROM gold_table WHERE risk_score IS NULL` = 0 |
| Score bounds | `SELECT MIN(risk_score), MAX(risk_score) FROM gold_table` — both in [0, 1] |
| Weights sum | Verify from `score_explanation` JSON that weights sum to 1.0 |
| Tier consistency | Every `risk_tier` maps correctly to the score range in RISK_TIERS config |
| Geometry preserved | `SELECT COUNT(*) FROM gold_table WHERE geometry IS NULL` = 0 |
