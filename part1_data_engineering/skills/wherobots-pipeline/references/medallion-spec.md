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
| **CRS tagging** | Sedona auto-detects raster CRS from GeoTIFF metadata — do not blanket-apply `RS_SetSRID(raster, 4326)`. Document source CRS in a `crs` STRING column per table (e.g., `EPSG:32611` for OPERA DSWx-S1, `EPSG:5070` for USFS CONUS rasters). All vector data is in EPSG:4326. |
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
| **Per-entity granularity** | Every Silver table has exactly one row per entity (building, parcel, asset). Aggregation is complete — no duplicate entity rows. **Exception**: temporal tables (see below). |
| **AOI-filtered** | Only entities within the declared AOI polygon appear. |
| **Temporally bounded** | All event/observation data is filtered to the declared temporal windows. Window boundaries are recorded in the table. Use **per-source** temporal windows — different data sources rarely share the same observation period. |
| **NULL semantics** | Missing data is NULL, not 0 or -1. NULL means "no data available", not "no risk". |
| **Coverage flags** | The unified enriched table includes boolean `has_<source>_data` flags to distinguish "no data" from "no risk". |
| **Independent enrichments** | Each hazard/signal source has its own Silver table. Reprocessing one does not require reprocessing others. |
| **Unified conflation** | The final Silver output (`asset_enriched`) LEFT JOINs all 1:1 enrichment tables onto the entity base. Temporal tables are kept separate (see below). |

### Temporal (Multi-Row) Silver Tables

Some sources produce multiple rows per entity (e.g., weekly flood observations). These must
**not** be joined into `asset_enriched` — doing so fans out the 1:1 table and breaks all
downstream assumptions.

**Pattern**: Write temporal data to its own Silver Iceberg table (e.g., `asset_flood_exposure`
with one row per asset × week). Gold loads this table separately, aggregates to per-asset,
then LEFT JOINs the aggregates onto the enriched data.

**Single-pass GROUP BY**. Derive the temporal bucket from the raw timestamp column
(e.g., `DATE_TRUNC('WEEK', acq_date)` for weekly) inside the SELECT and GROUP BY, then
write once with `writeTo(TABLE).createOrReplace()`.

### What Silver Does NOT Do
- No normalization to [0, 1] (that's Gold)
- No industry-specific weighting (that's Gold)
- No risk tier classification (that's Gold)
- No derived business metrics (that's Gold)

### Table Naming Convention
```
org_catalog.silver.asset_<source>_<operation>
org_catalog.silver.asset_enriched           # Always the final unified table (1:1)
```
Examples:
- `org_catalog.silver.asset_wildfire_exposure` (1:1 per asset)
- `org_catalog.silver.asset_flood_exposure` (temporal: 1 row per asset × week)
- `org_catalog.silver.asset_weather_density` (1:1 per asset)
- `org_catalog.silver.asset_enriched` (1:1 — wildfire + weather only, NO flood)

### Spatial Operation Selection Guide

Choose the correct spatial operation based on the source data type and the question being asked:

| Source Type | Question | Operation | Sedona Function |
|-------------|----------|-----------|----------------|
| Raster (single-band) | "What is the value at this location?" | Zonal Statistics (3-arg) | `RS_ZonalStats(raster, geometry, 'mean')` |
| Raster (multi-band) | "What is band N's value?" | Zonal Statistics (5-arg) | `RS_ZonalStats(raster, geometry, band_idx, 'max', true)` |
| Raster | "Does this location intersect a hazard zone?" | Raster-Vector Filter | `RS_Intersects(raster, geometry)` |
| Vector (events) | "How many events are near this location?" | KNN Spatial Join | `ST_KNN(a.geom, b.geom, k, true, radius)` |
| Vector (events) | "What is the nearest event?" | KNN (k=1) | `ST_KNN(a.geom, b.geom, 1, true, radius)` |
| Vector (polygons) | "Does this location fall within a zone?" | Spatial Join | `ST_Intersects(a.geometry, b.geometry)` |
| Vector (polygons) | "How much of the zone overlaps?" | Intersection Area | `ST_Area(ST_Intersection(a.geom, b.geom))` |

**RS_ZonalStats critical notes**:
- 3-arg form: `RS_ZonalStats(raster, geometry, 'mean')` — for single-band rasters only.
  Do NOT add a 4th arg (e.g., `true`) — Sedona interprets the stat name as band index.
- 5-arg form: `RS_ZonalStats(raster, geometry, 1, 'max', true)` — band index (1-based),
  stat type, allTouched/excludeNoData. Use for multi-band rasters or when features are
  smaller than pixel resolution.
- For sub-pixel features (building footprints < 30m raster pixels), prefer `allTouched=true`
  (5th arg) over `ST_Buffer`. Buffering causes a full geometry shuffle; allTouched is free.

**CRS handling (Sedona 0.12+)**:
- `RS_ZonalStats` and `RS_Intersects` **auto-reproject** the raster to match the geometry's
  CRS. No manual `ST_Transform` is required as long as both sides have a known CRS.
- This means OPERA (EPSG:32611), USFS wildfire (EPSG:5070), and Overture buildings
  (EPSG:4326) can be joined without explicit projection, provided each raster source has
  its native CRS embedded in the GeoTIFF.
- If a raster source lacks embedded CRS metadata, `RS_SetSRID(raster, <actual_srid>)` is
  required — but only when truly missing, not as a routine step.

**ST_KNN critical note (EPSG:4326 inputs)**:
- `ST_KNN(a.geom, b.geom, k, use_sphere, radius)` — `use_sphere` **must be `TRUE`** when
  inputs are lon/lat (EPSG:4326). With `use_sphere=FALSE`, `radius` is interpreted as
  degrees, producing silently wrong results (a 25km radius becomes ~0.0002 degrees of
  search, matching almost nothing, or a 25000 radius matches the whole globe).

### Required Columns in `asset_enriched`

| Column | Type | Source |
|--------|------|--------|
| `asset_id` | STRING | Entity identifier from the base table |
| `geometry` | GEOMETRY | Entity geometry from the base table |
| `<entity_attributes>` | varies | Key attributes from the base table (e.g., height, num_floors, class) |
| `<hazard_metrics>` | DOUBLE / INT | Raw metric columns from each 1:1 enrichment table |
| `has_<source>_data` | BOOLEAN | Coverage flag per enrichment source |
| `weather_window_start` | STRING | Weather observation window start (per-source) |
| `weather_window_end` | STRING | Weather observation window end (per-source) |

Note: Temporal window columns are per-source (e.g., `weather_window_start/end` for weather data).
Flood temporal metadata lives in the separate flood table, not in enriched.

---

## Gold Layer — Industry-Specific Scoring

### Purpose
Apply the 5-step scoring framework (select source metrics, normalize, weight, classify, derive)
to produce industry-specific risk scores and derived business metrics.

### Guarantees

| Guarantee | What It Means |
|-----------|--------------|
| **Same entity count as Silver** | Every entity from `asset_enriched` appears in every Gold table. No rows dropped. |
| **Per-industry source metrics** | Each industry uses different raw columns for its hazard factors (e.g., Insurance uses `flood_duration_days`, CRE uses `flood_max_wtr_class`). This produces genuinely different rank orderings and map distributions. |
| **Normalized factors** | All hazard factors are in [0, 1] range via min-max scaling. The superset of source columns is normalized once; each industry maps its columns from the pool. |
| **Weights sum to 1.0** | Per-industry weights for all factors sum to exactly 1.0. |
| **Risk score in [0, 1]** | The weighted composite score is bounded. |
| **Quantile-based risk tiers** | Tiers are assigned via `percent_rank()` percentile cuts, NOT fixed score thresholds. This guarantees a visually balanced map distribution (~5% critical / 15% high / 30% elevated / 30% moderate / 20% low) regardless of score skew. |
| **Score explanation** | Every row has a JSON column breaking down the score into its component factors, weights, and source column names. |
| **AOI-relative** | Normalization min/max are computed from the current AOI. Scores are NOT comparable across different AOIs. |
| **Temporal aggregation** | Weekly/temporal Silver tables are aggregated to per-asset in Gold before joining onto the enriched data. |

### What Gold Does NOT Do
- No new spatial operations (all spatial work is done in Silver)
- No data ingestion (all data comes from `asset_enriched` + temporal Silver tables)

### Table Naming Convention
```
org_catalog.gold.<industry_or_usecase>_<metric_type>
```
Examples:
- `org_catalog.gold.insurance_exposure`
- `org_catalog.gold.cre_risk`
- `org_catalog.gold.capital_markets_signals`
- `org_catalog.gold.energy_asset_risk`

### Gold Data Loading Pattern

```python
# 1. Load enriched (1:1 per asset — wildfire + weather)
enriched = sedona.table(ENRICHED_TABLE)

# 2. Load temporal table separately, aggregate to per-asset
flood_weekly = sedona.table(FLOOD_TABLE)
flood_agg = flood_weekly.groupBy("asset_id").agg(
    F.max("flood_max_wtr_class").alias("flood_max_wtr_class"),
    F.sum(F.when(F.col("flood_max_wtr_class") >= 1, 1).otherwise(0)).alias("flood_event_count"),
    F.datediff(F.max("flood_week"), F.min("flood_week")).alias("flood_duration_days"),
)

# 3. LEFT JOIN aggregates onto enriched
enriched = enriched.join(flood_agg, on="asset_id", how="left")
```

### Required Columns in Every Gold Table

| Column | Type | Description |
|--------|------|-------------|
| `asset_id` | STRING | Entity identifier |
| `geometry` | GEOMETRY | Entity geometry |
| `wildfire_factor` | DOUBLE | Normalized factor (0-1), from industry-specific source column |
| `flood_factor` | DOUBLE | Normalized factor (0-1), from industry-specific source column |
| `severe_weather_factor` | DOUBLE | Normalized factor (0-1), from industry-specific source column |
| `risk_score` | DOUBLE | Weighted composite (0-1) |
| `risk_tier` | STRING | Categorical tier via percentile cuts |
| `score_explanation` | STRING (JSON) | Factor weights, values, and source column names |
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
| Tier distribution balanced | Each industry should have ~5/15/30/30/20% tier split (quantile tiers) |
| Industries differ | Tier distributions should visibly differ across industries (different source metrics) |
| Source columns documented | `score_explanation` JSON includes `source_wildfire`, `source_flood`, `source_severe_weather` |
| Temporal table separate | `asset_enriched` has 1:1 rows; weekly data in separate table |
| Flood aggregates joined | Gold `COUNT(*)` matches enriched `COUNT(*)` after LEFT JOIN of flood aggregates |
| Tier consistency | Every `risk_tier` matches its `RISK_PERCENTILES` cut (e.g., `critical` = top 5% of `risk_score` by `percent_rank`) |
| Geometry preserved | `SELECT COUNT(*) FROM gold_table WHERE geometry IS NULL` = 0 |
