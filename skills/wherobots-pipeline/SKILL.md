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

## Workflow

Follow these phases in order. Do not skip or proceed until each phase's output is confirmed.

### Phase 1 — Requirements

Collect before touching any tools: (1) Use case — what question does the pipeline answer?
(2) Geographic scope — what AOI? (3) Industry vertical — who consumes the output?
If vague, ask. Do not assume.

### Phase 2 — Data Discovery (MCP-First)

Use Wherobots MCP tools to ground the pipeline in real, available data:
`search_documentation` → `list_catalogs` → `list_databases` → `list_tables` → `describe_table`.
Present discovered datasets to user. Wait for confirmation.

### Phase 3 — Pipeline Design

Read `./references/medallion-spec.md` for layer contracts and the spatial operation selection guide.

Produce a design document: (1) ASCII pipeline diagram, (2) table inventory with catalog paths
and schemas, (3) notebook plan with execution order, (4) spatial operation plan, (5) Gold
scoring design with factors, proposed weights, and derived metrics.
Present to user. Wait for approval.

### Phase 4 — Generate Documentation

From the approved design, produce `architecture.md` (pipeline diagram, component descriptions,
data flow) and `data_dictionary.md` (every table, every column, types, descriptions). These
serve as the attendee's reference while notebooks are generated.

### Phase 5 — Generate Notebooks

Generate `raw-to-bronze.ipynb`, `bronze-to-silver.ipynb`, `silver-to-gold.ipynb` following the
layer contracts in medallion-spec.md. After each notebook, audit against the gotchas below.

### Phase 6 — Verification & Reconciliation

Use MCP `execute_query` to verify every table (`COUNT(*)` + `LIMIT 5`). If notebook generation
changed any table names or columns from the original design, update the docs to match.
Present summary to user.

---

## Gold Scoring Process

4-step framework applied in Gold: **Normalize** (min-max to [0,1], clamp, NULL→0, handle
min==max) → **Weight** (per-industry, must sum to 1.0) → **Classify** (Critical≥0.80,
High≥0.60, Elevated≥0.40, Moderate≥0.20, Low<0.20) → **Derive** (industry-specific metrics).

Scoring is AOI-relative — NOT comparable across different AOIs.

**Designing weights for a new industry**: Identify the primary decision → rank hazards by
impact (most impactful: 0.35-0.50) → distribute remaining (sum to 1.0) → select 2-4 derived
metrics → document rationale → propose to user and wait for confirmation.

---

## Sedona / Wherobots Gotchas

These are the mistakes LLMs consistently make. Use `search_documentation` MCP tool for general
API reference; this section covers only the non-obvious traps.

| Rule | Wrong | Right |
|------|-------|-------|
| Session variable | `spark.read`, `spark.sql` | `sedona.read`, `sedona.sql` (after `SedonaContext.create()`) |
| Point arg order | `ST_Point(lat, lon)` | `ST_Point(lon, lat)` — X, Y |
| Geodesic distance | `ST_Distance` (returns degrees) | `ST_DistanceSpheroid` (returns meters) |
| Raster CRS | Use raster immediately after load | `RS_SetSRID(raster, 4326)` before any operation |
| Raster intersection | `RS_Intersects(geometry, raster)` | `RS_Intersects(raster, geometry)` — raster first |
| Zonal stats | No GROUP BY → duplicate rows | `GROUP BY asset_id, geometry` (assets span tiles) |
| Iceberg write | `df.write.format("iceberg").save()` | `df.writeTo("...").createOrReplace()` |
| Iceberg read | `sedona.read.format("iceberg").load()` | `sedona.table("catalog.db.table")` |
| S3 anon creds | Global anonymous provider | Per-bucket: `fs.s3a.bucket.<NAME>.aws.credentials.provider` |
| Missing data | `df.fillna(0)` | Keep NULLs + `has_<source>_data` flags |
| Snapshot cleanup | None after createOrReplace | `expire_snapshots(retain_last => 1)` |

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

### ipynb Format

Valid JSON: `nbformat: 4`, `nbformat_minor: 5`. Each source line ends with `\n`.
Code cells: `"outputs": [], "execution_count": null`. Markdown cells: no outputs field.
