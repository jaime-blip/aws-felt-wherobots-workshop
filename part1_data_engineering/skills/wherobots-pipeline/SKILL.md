---
name: wherobots-pipeline
description: |
  Build geospatial data pipelines on Wherobots Cloud using medallion architecture (Bronze/Silver/Gold).
  Use when: building data engineering notebooks, creating spatial ETL pipelines, designing risk scoring
  or analytics models on geospatial data, or generating medallion-architecture pipelines for any industry.
  Requires: Wherobots MCP server connected. Produces: Jupyter notebooks (.ipynb) + documentation.
---

# Wherobots Pipeline Skill

Build geospatial data pipelines on Wherobots Cloud. Produces Jupyter notebooks implementing
medallion architecture (Bronze → Silver → Gold) for any industry vertical.

## How the MCP generates code — what this skill layers on top

The Wherobots MCP's `generate_spatial_query_tool` is a **single-query SQL generator**, not a
notebook generator. Each call:

1. Takes your natural-language prompt.
2. Retrieves top-N Wherobots documentation snippets via RAG and injects them into the
   generation prompt.
3. Calls an LLM and returns raw SQL wrapped in JSON.

### What the MCP does for you automatically

- **Read-only enforcement** — rejects `INSERT`, `UPDATE`, `DELETE`, etc. server-side.
- **LIMIT/OFFSET auto-injection** on outer SELECTs to cap result size.
- **Documentation grounding** — each generation call automatically pulls relevant
  Wherobots docs into the prompt (you don't need to do `search_documentation` first).
- **Discovery workflow** — tool descriptions push the `docs → catalogs → tables →
  describe_table → generate → execute` sequence.

You do not need to restate any of the above in your prompts.

### What the MCP does NOT do — the skill's job

- **No medallion awareness.** It has no concept of Bronze/Silver/Gold, layer contracts,
  or pipeline stages. Orchestrating the 3-notebook sequence is entirely the skill's job.
- **No notebook output.** The MCP returns a SQL string. Wrapping it in `.ipynb` cells
  (config / init / transform / verify / cleanup) is the skill's job.
- **No Wherobots/Sedona idioms in the generation prompt.** The LLM that the MCP calls
  does not receive guidance on `sedona.sql` vs `spark.sql`, `.writeTo().createOrReplace()`
  vs `.write.format("iceberg")`, `sedona.table()` for Iceberg reads, or the `ST_Point(lon, lat)`
  argument order. If you want Wherobots-idiomatic code, you must either (a) include the
  rules in the natural-language prompt you pass to `generate_spatial_query_tool`, or
  (b) post-process the returned SQL yourself.
- **No CRS gotchas.** `use_sphere=TRUE` for `ST_KNN`, auto-reproject behavior, per-source
  CRS tagging — none of these are in the generation prompt. Pass them in yours.
- **No Gold scoring opinions.** `INDUSTRY_FACTORS`, `percent_rank()` tiers, score-explanation
  JSON — the MCP will happily generate fixed-threshold tiers with identical columns across
  industries unless your prompt tells it otherwise.
- **No multi-query patterns.** The week-by-week flood append loop (see below) is a Python
  for-loop around many single-query MCP calls. The MCP cannot emit that structure itself.

**Practical consequence.** When you call `generate_spatial_query_tool`, your natural-language
prompt must embed the Wherobots-specific requirements you want reflected in the output.
See **Prompts to pass to `generate_spatial_query_tool`** below for reusable templates.

---

## Workflow

Follow these phases in order. Do not skip or proceed until each phase's output is confirmed.

### Phase 1 — Requirements

Collect before touching any tools: (1) Use case — what question does the pipeline answer?
(2) Geographic scope — what AOI? (3) Industry vertical — who consumes the output?
If vague, ask. Do not assume.

### Phase 2 — Data Discovery (MCP-First)

Use the MCP's discovery tools to ground the pipeline in real, available data. The MCP pushes
the recommended order (`docs → catalogs → tables → describe_table`) via its tool descriptions;
follow it.

**Critical, and not enforced by the MCP:**
- Always `describe_table` before designing. Do NOT assume schemas from documentation or
  dataset names.
- For raster tables, check band distributions (`SELECT DISTINCT band FROM ...`) and sample
  `RS_Metadata(raster)` to confirm the source CRS and pixel scale.
- Confirm the CRS of every raster source before picking spatial operations (see CRS gotchas
  below).

Present discovered datasets to user. Wait for confirmation.

### Phase 3 — Pipeline Design

Read `./references/medallion-spec.md` for layer contracts and the spatial operation selection guide.

Produce a design document: (1) ASCII pipeline diagram, (2) table inventory with catalog paths
and schemas, (3) notebook plan with execution order, (4) spatial operation plan, (5) Gold
scoring design with per-industry source metrics, proposed weights, and derived metrics.
Present to user. Wait for approval.

### Phase 4 — Generate Documentation

From the approved design, produce `architecture.md` (pipeline diagram, component descriptions,
data flow) and `data_dictionary.md` (every table, every column, types, descriptions). These
serve as the attendee's reference while notebooks are generated.

### Phase 5 — Generate Notebooks

Generate `raw-to-bronze.ipynb`, `bronze-to-silver.ipynb`, `silver-to-gold.ipynb` following the
layer contracts in medallion-spec.md. For each SQL-heavy cell, call `generate_spatial_query_tool`
using one of the reusable prompt templates in **Prompts to pass to `generate_spatial_query_tool`**
below — the templates embed the Wherobots-specific requirements that the MCP's generation
prompt does not inject on its own. After each notebook, audit against the gotchas table below.

### Phase 6 — Verification & Reconciliation

Use MCP `execute_query` to verify every table (`COUNT(*)` + `LIMIT 5`). If notebook generation
changed any table names or columns from the original design, update the docs to match.
Present summary to user.

---

## Gold Scoring Process

### 5-Step Framework

Applied in Gold for each industry:

1. **Select** — Choose industry-specific source metrics for each hazard factor (see below)
2. **Normalize** — Min-max to [0,1], clamp, NULL→0, handle min==max. Normalize the
   *superset* of all source columns used across industries in one pass, producing `norm_*` columns.
3. **Weight** — Per-industry factor weights, must sum to 1.0.
4. **Classify** — Quantile-based tiers via `percent_rank()` (see tier scheme below).
5. **Derive** — Industry-specific business metrics.

Scoring is AOI-relative — NOT comparable across different AOIs.

### Per-Industry Source Metrics (Critical for Differentiation)

**Problem**: If all industries normalize the same 3 columns and only change weights, the rank
ordering barely changes → all industries get nearly identical tier distributions on the map.

**Solution**: Each industry must use different raw source columns for its hazard factors. This
produces genuinely different rank orderings and visually distinct maps.

When designing a pipeline, map each industry to the *aspect* of each hazard that matters most:

| Aspect | Example Column | Best For |
|--------|----------------|----------|
| Average risk | `burn_prob_mean` | Insurance (claim frequency), CapMarkets (portfolio risk) |
| Worst-case risk | `burn_prob_max` | CRE (go/no-go screening) |
| Intensity | `flame_length_mean` | Energy (ignition risk) |
| Duration | `flood_duration_days` | Insurance (sustained claims exposure) |
| Peak severity | `flood_max_wtr_class` | CRE (deal-breaker threshold) |
| Frequency | `flood_event_count` | CapMarkets, Energy (recurrence) |
| Broad area count | `event_count_25km` | Insurance (wide-area exposure) |
| Local intensity | `event_count_5km` | Energy (at-the-asset impacts) |
| Proximity | inverse distance to nearest event | CRE (nearby = deal-breaker) |
| Peak event severity | `max_hail_sevprob` | CapMarkets (supply chain disruption) |

Store the mapping in an `INDUSTRY_FACTORS` dict in the config cell:
```python
INDUSTRY_FACTORS = {
    "insurance": {
        "wildfire_factor": "burn_prob_mean",
        "flood_factor":    "flood_duration_days",
        "severe_weather_factor": "event_count_25km",
    },
    # ... different columns for each industry
}
```

Use a helper function (e.g., `add_industry_factors()`) to map each industry's `norm_*` columns
→ `wildfire_factor`, `flood_factor`, `severe_weather_factor`, `risk_score`.

### Quantile-Based Risk Tiers

**Do NOT use fixed score thresholds** (e.g., Critical≥0.80). With right-skewed hazard data,
fixed thresholds produce extreme imbalance (e.g., 882K low, 65 critical) making maps useless.

Use `percent_rank()` over `risk_score` to cut tiers by percentile:

```python
RISK_PERCENTILES = {
    "critical": 0.95,   # top 5%
    "high":     0.80,   # 80th–95th percentile
    "elevated": 0.50,   # 50th–80th percentile
    "moderate": 0.20,   # 20th–50th percentile
    "low":      0.00,   # bottom 20%
}

def classify_risk_tier(score_col: str) -> F.Column:
    pct = F.percent_rank().over(Window.orderBy(F.col(score_col).asc()))
    return (
        F.when(pct >= RISK_PERCENTILES["critical"], F.lit("critical"))
         .when(pct >= RISK_PERCENTILES["high"],     F.lit("high"))
         .when(pct >= RISK_PERCENTILES["elevated"], F.lit("elevated"))
         .when(pct >= RISK_PERCENTILES["moderate"], F.lit("moderate"))
         .otherwise(F.lit("low"))
    )
```

This guarantees a visually balanced map (~5/15/30/30/20 split) regardless of score skew.
Combined with per-industry source metrics, each industry will have genuinely different tier
assignments despite using the same percentile cuts.

### Designing Factors for a New Industry

1. Identify the industry's primary decision (underwrite, acquire, divest, harden)
2. For each hazard, ask: "Which *aspect* drives that decision?" (severity? duration? proximity? frequency?)
3. Choose the raw column that best captures that aspect
4. Rank hazards by impact → assign weights (most impactful: 0.35–0.50, sum to 1.0)
5. Select 2–4 derived metrics specific to the industry
6. Document rationale → propose to user → wait for confirmation

### Score Explanation JSON

Include source column names in the `score_explanation` JSON so downstream consumers know
exactly which metrics drove the score:
```python
F.lit(factors["wildfire_factor"]).alias("source_wildfire"),
F.lit(factors["flood_factor"]).alias("source_flood"),
F.lit(factors["severe_weather_factor"]).alias("source_severe_weather"),
```

---

## RS_ZonalStats Signatures (Critical)

The function signature changes based on whether you need band selection and allTouched:

| Form | Signature | When to Use |
|------|-----------|-------------|
| 3-arg (single-band) | `RS_ZonalStats(raster, geometry, 'mean')` | Single-band rasters (e.g., wildfire burn probability) |
| 5-arg (multi-band + allTouched) | `RS_ZonalStats(raster, geometry, 1, 'max', true)` | Multi-band rasters with band selection; `true` = allTouched/excludeNoData |

**Traps**:
- Do NOT add `true` as a 4th arg to the 3-arg form. Sedona will interpret the stat name as a
  band index and fail with a confusing error.
- For sub-pixel features (building footprints < 30m pixel), use the 5-arg form with
  `allTouched=true` instead of buffering the geometry. This is faster and avoids the full
  shuffle that `ST_Buffer` requires.

---

## Flood Data: OPERA DSWx-S1

When using OPERA DSWx-S1 for flood data (`org_catalog.opera.dswx_s1`):

- **Band B01_WTR** is the primary water classification band. Sufficient for most use cases.
  Using all 4 bands (B01_WTR, B02_BWTR, B03_CONF, B04_DIAG) is 4× slower with
  marginal improvement — only use all bands if the user specifically requests confidence weighting.
- **CRS is EPSG:32611** (UTM Zone 11N for San Diego). Verify CRS via MCP for other AOIs.
- **Temporal filtering**: Filter by `acq_date BETWEEN start AND end` and `band = 'B01_WTR'`.
- **Weekly granularity**: Use `DATE_TRUNC('week', acq_date)` to aggregate into weekly bins
  in Silver. This reduces row count while preserving temporal signal.

### Week-by-Week Iceberg Append (Shuffle Reduction)

For large flood datasets, processing all weeks at once causes excessive Spark shuffle
(buildings × all tiles). Instead, iterate one week at a time:

```python
for i, (week_start, week_end) in enumerate(week_boundaries):
    week_df = ...  # filter flood tiles to this week, join + zonal stats
    if i == 0:
        week_df.writeTo(TABLE).createOrReplace()
    else:
        week_df.writeTo(TABLE).append()
```

This caps shuffle at buildings × 1 week of tiles per iteration.

### Flood Metrics Available After Aggregation

The weekly flood table produces these per-asset aggregates for Gold:
- `flood_event_count` — count of weeks with WTR ≥ 1 (frequency)
- `flood_duration_days` — days between first and last flood week (duration)
- `flood_max_wtr_class` — peak WTR classification across all weeks (severity)

Different industries should use different flood metrics (see Per-Industry Source Metrics above).

---

## Silver: Deferred Joins for Weekly Data

When a Silver source has temporal granularity (e.g., weekly flood rows), do NOT join it into
`asset_enriched` — this would fan out the 1:1 enriched table into N rows per asset, breaking
downstream assumptions.

Instead:
1. Write the weekly data to its own Silver Iceberg table (e.g., `asset_flood_exposure`)
2. The `asset_enriched` table contains only 1:1 data (wildfire + weather)
3. Gold loads the weekly table separately, aggregates to per-asset, then LEFT JOINs

This preserves the enriched table's 1:1 guarantee while keeping weekly granularity available.

---

## Temporal Window Configuration

Use separate temporal windows for each data source — they rarely share the same observation period:

```python
FLOOD_WINDOW_START   = "2025-12-01"
FLOOD_WINDOW_END     = "2026-03-31"
WEATHER_WINDOW_START = "2025-01-01"
WEATHER_WINDOW_END   = "2026-03-25"
```

**Trap**: Never use a single `WINDOW_START`/`WINDOW_END` for all sources. Flood data may cover
a 4-month event window while weather data covers 15 months. A single window will silently
produce empty results for one source.

---

## Prompts to pass to `generate_spatial_query_tool`

The MCP's generation prompt injects relevant documentation but does NOT inject Wherobots
idioms (`.writeTo()`, `sedona.sql`), CRS rules (`use_sphere=TRUE`), or scoring framework
(`percent_rank()`, `INDUSTRY_FACTORS`). Embed them in the natural-language prompt you pass.

Templates below are starting points. Substitute `{bracketed}` fields.

### Bronze — CSV → Iceberg

> Generate Sedona SQL that ingests `{s3_csv_path}` into Iceberg table `{target_table}`.
> Columns: `{col_list}`. Parse `{timestamp_col}` via `to_timestamp('yyyyMMddHHmmss')`.
> Cast `{numeric_cols}` to double. Build a geometry via `ST_Point(CAST(LON AS DOUBLE),
> CAST(LAT AS DOUBLE))` (x=lon, y=lat), then drop LON and LAT. Use `sedona.read` (not
> `spark.read`). Materialize via `df.writeTo("{target_table}").createOrReplace()`.

### Bronze — raster ingest

> Generate Sedona SQL that ingests `{s3_geotiff_path}` into Iceberg table `{target_table}`.
> Use `sedona.read.format("raster").option("tileWidth", 128).option("tileHeight", 128)`.
> Rename the `rast` column to `raster`. Compute `geometry = RS_Envelope(raster)`. Add a
> `crs` STRING column with the source CRS (e.g., 'EPSG:32611' for OPERA, 'EPSG:5070' for
> USFS CONUS rasters). Do NOT call `RS_SetSRID` — Sedona auto-detects CRS from the GeoTIFF
> metadata. Materialize via `df.writeTo("{target_table}").createOrReplace()`.

### Silver — zonal statistics (raster → vector)

> Generate Sedona SQL that joins `{raster_table}` to `{buildings_table}` (filtered to the
> AOI polygon) via `RS_Intersects(raster, geometry)` — raster first. For each building,
> compute `RS_ZonalStats(raster, geometry, 'mean')` and `RS_ZonalStats(raster, geometry,
> 'max')`. `GROUP BY asset_id, geometry` because assets can span multiple raster tiles.
> `RS_ZonalStats` and `RS_Intersects` auto-reproject across CRSs in Sedona 0.12+ — no
> manual `ST_Transform` needed. If features are smaller than the raster pixel, use the
> 5-arg form `RS_ZonalStats(raster, geometry, 1, 'max', true)` with `allTouched=true`
> instead of buffering. Do NOT add a 4th arg to the 3-arg form.

### Silver — KNN event density (vector → vector)

> Generate Sedona SQL for a KNN spatial join between `{buildings}` (EPSG:4326) and
> `{events_table}` (EPSG:4326 points). Use
> `ST_KNN(b.geometry, e.geometry, 10, TRUE, 25000)` — `use_sphere=TRUE` is **mandatory**
> for lat/lon inputs; without it, the 25000 radius is interpreted in degrees and results
> are meaningless. Use `ST_DistanceSpheroid` (not `ST_Distance`) for the distance column
> so it returns meters. Filter events to `ZTIME BETWEEN {WEATHER_WINDOW_START} AND
> {WEATHER_WINDOW_END}`. Aggregate to one row per asset.

### Silver — one week of flood (wrap in a Python for-loop in the notebook)

> Generate Sedona SQL for ONE ISO week of flood. Filter `org_catalog.opera.dswx_s1` to
> `acq_date BETWEEN DATE('{week_start}') AND DATE('{week_end}')` and `band = 'B01_WTR'`.
> Join to `{buildings}` via `RS_Intersects(raster, geometry)`, compute
> `MAX(RS_ZonalStats(raster, geometry, 1, 'max', true))` per asset with `allTouched=true`.
> Emit one `DATE('{week_start}') AS flood_week` column. Return a single SELECT. The
> notebook wraps this query in a for-loop over week boundaries: first iteration
> `.writeTo(FLOOD_SILVER).createOrReplace()`, subsequent iterations `.append()`.

### Gold — industry-specific scoring

> Generate Sedona SQL that scores `{enriched_table}` for industry `{industry}` using
> `INDUSTRY_FACTORS['{industry}']` to pick source columns (do NOT reuse the same 3 columns
> across industries). Normalize each chosen source column via min-max to [0,1], treating
> NULL as 0. Compute
> `risk_score = norm_wildfire_factor * {w_wf} + norm_flood_factor * {w_fl} + norm_severe_weather_factor * {w_sw}`
> where the three weights sum to 1.0. Classify `risk_tier` via
> `percent_rank()` over `risk_score` ordered ascending, cut at percentiles 0.95 (critical),
> 0.80 (high), 0.50 (elevated), 0.20 (moderate), else low — do NOT use fixed score
> thresholds like `score >= 0.80`. Emit a `score_explanation` JSON column with the source
> column names (`source_wildfire`, `source_flood`, `source_severe_weather`) and weights.

### After the MCP returns

Audit the returned SQL for the anti-patterns below before putting it in a notebook cell.
The MCP occasionally emits `.write.format("iceberg")` or `spark.sql(...)` despite the
prompt; translate to `.writeTo().createOrReplace()` and `sedona.sql(...)` respectively.

---

## Sedona / Wherobots Gotchas

These are the mistakes LLMs consistently make. Use `search_documentation` MCP tool for general
API reference; this section covers only the non-obvious traps.

| Rule | Wrong | Right |
|------|-------|-------|
| Session variable | `spark.read`, `spark.sql` | `sedona.read`, `sedona.sql` (after `SedonaContext.create()`) |
| Point arg order | `ST_Point(lat, lon)` | `ST_Point(lon, lat)` — X, Y |
| Geodesic distance | `ST_Distance` (returns degrees) | `ST_DistanceSpheroid` (returns meters) |
| KNN on EPSG:4326 points | `ST_KNN(a.geom, b.geom, k, FALSE, radius)` | `ST_KNN(a.geom, b.geom, k, TRUE, radius_m)` — **`use_sphere=TRUE` is mandatory** for lat/lon data; without it, `radius` is in degrees and results are meaningless |
| Raster CRS | `RS_SetSRID(raster, 4326)` regardless of source | Sedona auto-detects CRS from GeoTIFF metadata. Document source CRS in a `crs` STRING column. Only call `RS_SetSRID` when the source truly lacks an embedded SRID (rare). |
| Cross-CRS raster↔vector ops | Manual `ST_Transform` to match raster and vector CRS | `RS_ZonalStats` / `RS_Intersects` auto-reproject in Sedona 0.12+ — no manual transform needed if both sides have a known CRS |
| Raster intersection | `RS_Intersects(geometry, raster)` | `RS_Intersects(raster, geometry)` — raster first |
| Zonal stats 3-arg | `RS_ZonalStats(raster, geom, 'mean', true)` | `RS_ZonalStats(raster, geom, 'mean')` — no 4th arg for single-band |
| Zonal stats 5-arg | `RS_ZonalStats(raster, geom, 'max')` for multi-band | `RS_ZonalStats(raster, geom, 1, 'max', true)` — band index + allTouched |
| Zonal stats aggregation | No GROUP BY → duplicate rows | `GROUP BY asset_id, geometry` (assets span tiles) |
| Sub-pixel footprints | `ST_Buffer(geometry, 30)` then zonal stats | Use `allTouched=true` (5th arg) — faster, no extra shuffle |
| Iceberg write | `df.write.format("iceberg").save()` | `df.writeTo("...").createOrReplace()` |
| Iceberg append | `df.writeTo("...").createOrReplace()` in loop | First iteration: `.createOrReplace()`, subsequent: `.append()` |
| Iceberg read | `sedona.read.format("iceberg").load()` | `sedona.table("catalog.db.table")` |
| S3 anon creds | Global anonymous provider | Per-bucket: `fs.s3a.bucket.<NAME>.aws.credentials.provider` |
| Missing data | `df.fillna(0)` | Keep NULLs + `has_<source>_data` flags |
| Snapshot cleanup | None after createOrReplace | `expire_snapshots(retain_last => 1)` |
| Weekly data in enriched | LEFT JOIN weekly rows onto enriched | Keep weekly table separate; aggregate in Gold before joining |
| Same factors all industries | Same 3 source columns, different weights | Different source columns per industry via `INDUSTRY_FACTORS` |
| Fixed tier thresholds | `Critical≥0.80, High≥0.60` | `percent_rank()` with percentile cuts — immune to score skew |
| Temporal windows | Single `WINDOW_START/END` for all sources | Per-source windows: `FLOOD_WINDOW_*`, `WEATHER_WINDOW_*` |
| Config cell edits | Partial updates that truncate existing vars | Always verify ALL config variables survive after editing |

---

## Notebook Conventions

| Role | Type | Rule |
|------|------|------|
| Section header | Markdown | `## Name` + 1-2 sentence description |
| Configuration | Code | Single cell, top of notebook. ALL tunable params. UPPER_SNAKE_CASE. |
| Initialization | Code | `SedonaContext` setup. Exactly once per notebook. |
| Transform | Code | One logical operation per cell. |
| Verification | Code | Row count + `LIMIT 5`. End of each section. |
| Cleanup | Code | `expire_snapshots`. Last section. |

**New cell?** Different source → new section. Same source, different op → new cell.
**Temp view or Iceberg?** Within one notebook → temp view. Crosses notebooks → Iceberg.
**AOI filter at Bronze or Silver?** Silver. Broad regional filter at Bronze only if full extent is impractical.

**Config cell safety**: When editing the config cell, always read the full cell first and
verify that ALL existing variables (SCORING_WEIGHTS, RISK_PERCENTILES, INDUSTRY_FACTORS,
CRE_SCREEN_THRESHOLD, AURORA_SCHEMA, etc.) are preserved. Partial updates that truncate
the cell are a common failure mode.

### ipynb Format

Valid JSON: `nbformat: 4`, `nbformat_minor: 5`. Each source line ends with `\n`.
Code cells: `"outputs": [], "execution_count": null`. Markdown cells: no outputs field.
