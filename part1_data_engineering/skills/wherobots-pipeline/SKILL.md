---
name: wherobots-pipeline
description: |
  Build geospatial data pipelines on Wherobots Cloud using medallion architecture (Bronze/Silver/Gold).
  Use when: building data engineering notebooks, creating spatial ETL pipelines, designing risk scoring
  or analytics models on geospatial data, or generating medallion-architecture pipelines for any industry.
  Requires: Wherobots MCP server connected. Produces: Jupyter notebooks (.ipynb) + documentation.
---

# Wherobots Pipeline Skill

Build geospatial medallion pipelines on Wherobots Cloud. The Wherobots MCP's
`generate_spatial_query_tool` emits a single SQL query per call — it doesn't
know about notebook structure, medallion layers, or Wherobots idioms. This
skill tells the agent how to orchestrate MCP calls into notebooks AND when
to run the workshop's reference pipeline vs generate a custom one.

Details are in `./references/`:

- `medallion-spec.md` — layer contracts (Bronze/Silver/Gold guarantees)
- `gold-scoring.md` — per-industry source metrics, `percent_rank` tiers
- `opera-dswx-s1.md` — OPERA flood data specifics

---

## Participant mode — Explore / Run Reference / Generate Custom

The workshop ships a pre-generated reference pipeline and pre-loaded Gold
tables in Aurora as a safety net. The agent serves three modes from the
same chat; infer the mode from the participant's prompt.

### Explore

Participant is asking about the catalog, data shape, sample values,
"what do I have?". Use the Wherobots MCP discovery tools — `list_catalogs`,
`list_databases`, `list_tables`, `describe_table`, optionally
`execute_query_tool` for ad-hoc SELECTs. **Do not modify any files.**

If `org_catalog` is empty or missing the workshop bronze tables, do
not just report "it's empty" — follow the **Empty catalog** rule
below to onboard the participant and offer to bootstrap.

### Run Reference

Participant wants the shipped pipeline ("run the workshop pipeline",
"score San Diego buildings for insurance"). Execute the **reference
notebooks** — `part1_data_engineering/bronze-to-silver.ipynb` then
`part1_data_engineering/silver-to-gold.ipynb`.

**Config-cell parameter tweaks belong here, not in Generate Custom.**
Changing AOI bbox, scoring weights, temporal windows, or swapping to
a different industry already in `INDUSTRY_FACTORS` is a parameter edit
— make it in the reference notebook's config cell and re-run. No new
notebook needed.

### Generate Custom

Participant wants an **analysis change** that the config cell can't
express: a new hazard source (lightning, air quality), a new industry
not in `INDUSTRY_FACTORS`, new derived metrics, or a different scoring
structure. Generate new notebooks under `custom-pipelines/<short-name>/`
(create the directory if missing). Follow the Workflow below and every
rule in this skill.

If the ask is just new weights or a new AOI, don't default to a new
notebook — point the participant at the config cell in the existing
reference notebook instead. Ask if unclear.

### Empty catalog

If `org_catalog.{noaa_swdi,opera,wildfire_risk}` tables don't exist yet
when the participant asks to explore or run, **don't just say "run
bootstrap"**. Use it as an onboarding moment:

1. Acknowledge what they asked ("you want to see what's in your
   catalog / run the pipeline").
2. Tell them nothing's loaded yet — and what the workshop's bootstrap
   will provide. Give the one-line-per-dataset summary from Onboarding
   rule 1:
   - `org_catalog.noaa_swdi.{hail,tvs,structure,warn}` — NEXRAD storm
     radar observations (hail signatures, tornado vortex signatures,
     storm-cell structure)
   - `org_catalog.opera.dswx_s1` — NASA/JPL Sentinel-1 SAR flood
     classification rasters
   - `org_catalog.wildfire_risk.{burn_probability_conus, conditional_flame_length_conus}`
     — USFS CONUS wildfire burn probability + flame length rasters
3. Offer to run the bootstrap:
   > *"I can kick off `python3 scripts/run_bootstrap.py` to load all
   > seven bronze tables (~4 min on Tiny), or I can keep explaining
   > what each dataset contains first. Which do you prefer?"*
4. If they choose to bootstrap: run it, stream progress. If they want
   to learn first: describe each dataset's row semantics, typical use
   cases, and scale — THEN offer bootstrap again.

Don't fabricate data, don't skip the bootstrap step silently, don't
block exploration on having the data loaded (participants can ask
questions about the workshop datasets conceptually before running
bootstrap).

### Protected files — structure, not parameters

Do not add cells, restructure, or rewrite the analysis in the reference
notebooks:

- `part1_data_engineering/bronze-to-silver.ipynb`
- `part1_data_engineering/silver-to-gold.ipynb`

Config-cell parameter edits in those notebooks (AOI, weights, windows,
industry selector) are the intended use — they're fine. For analysis
changes (new source, new industry logic, new metrics), copy the
notebook into `custom-pipelines/<name>/` and edit the copy.

Never modify:

- `scripts/bootstrap.py`
- `scripts/run_bootstrap.py`

---

## Onboarding rules — teach as you go

Assume zero geospatial background. Every participant interaction is
partly collaboration, partly onboarding. Apply these across all three
modes — Explore, Run Reference, Generate Custom.

1. **Name the data before using it.** First mention of any dataset, add
   one sentence on what it is and what a row represents. *"`org_catalog.noaa_swdi.hail`
   is NOAA NEXRAD hail-radar reports — each row is one hail signature
   observation at a given location and time. You have ~25M rows for
   2024–2025."*
2. **Connect data to the participant's use case.** Before designing,
   map each hazard source to what it tells them about THEIR decision.
   *"For your warehouse-insurance question, OPERA DSWx-S1 tells us how
   often each warehouse sat in a flooded pixel — a claims-frequency
   signal, not a peak-depth signal."*
3. **Explain spatial ops in plain English before emitting SQL.** First
   mention of each operation gets a one-sentence gloss. *"`RS_ZonalStats` —
   for each polygon, compute a statistic over the raster pixels that
   overlap it. Here, average wildfire burn probability per building."*
4. **Show scale at computationally meaningful moments.** Before a large
   join, read, or write, tell the participant roughly what's about to
   be processed: rows in / out, size in GB, expected runtime on the
   current runtime. *"About to zonal-stat 358K buildings against 970K
   wildfire raster tiles. Expect ~30s on Tiny."*
5. **Collaborate on design choices — don't pre-pick.** Where this skill's
   rules allow more than one valid answer (which scoring weights, which
   source metric per factor, which derived metric, window size), present
   the options with plain-English tradeoffs and let the participant
   choose. Never secretly decide for them.
6. **Show artifacts after each step.** Don't just say "done" — after
   each notebook cell or silver/gold write, emit the row count, the
   column list, and 3–5 sample rows. Participants need to see the
   output to trust it.

Tone: 1–2 sentences per explanation, layered progressively. Not a
lecture — just enough context that the participant always knows what's
happening and why.

---

## Workflow (for Generate Custom mode only)

Follow in order. Don't skip phases; confirm each output before proceeding.

### Phase 1 — Requirements

Collect before touching any tools: (1) use case / question, (2) AOI,
(3) industry vertical. If vague, ask. Don't assume.
Onboard: rephrase the participant's business question in geospatial
terms before proceeding (rule 2).

### Phase 2 — Data Discovery (MCP-first)

Use the MCP's discovery tools to ground the pipeline in real, available
data. The MCP's tool descriptions push the right order — follow them.

Non-obvious and not enforced by the MCP:

- `describe_table` every source before designing. Do not assume schemas from
  documentation or dataset names.
- For rasters: sample `RS_Metadata(raster)` to confirm source CRS and pixel
  scale. Check band distributions via `SELECT DISTINCT band FROM ...`.
- `generate_spatial_query_tool` and `execute_query_tool` are useful for
  ad-hoc exploration SELECTs during discovery; for notebook cells,
  generate SQL directly using the rules in this skill.

Onboard: name each dataset + explain its rows + include a row count so
the participant feels the scale (rules 1, 2, 4). Present discovered
datasets to the user. Wait for confirmation.

### Phase 3 — Pipeline Design

Read `./references/medallion-spec.md`. Produce: ASCII pipeline diagram,
table inventory with catalog paths and schemas, notebook plan with
execution order, spatial-operation plan, Gold-scoring design (per-industry
source metrics, weights, derived metrics — see `./references/gold-scoring.md`).

Onboard: any design choice with more than one valid answer (weights,
source metrics, windows, derived metrics) is presented as **options
with tradeoffs**, not a pre-made decision (rule 5). Wait for approval.

### Phase 4 — Generate Documentation

Produce `architecture.md` and `data_dictionary.md` alongside the generated
notebooks under `custom-pipelines/<name>/`. These are the participant's
reference while notebooks are generated and run.

### Phase 5 — Generate Notebooks

Generate `raw-to-bronze.ipynb` (if needed), `bronze-to-silver.ipynb`,
`silver-to-gold.ipynb` following the layer contracts in medallion-spec.md.
Write notebook-cell SQL directly — don't round-trip every query through
`generate_spatial_query_tool`. After each notebook, audit against the
gotchas table below.

Onboard: every code cell gets a markdown cell above it explaining the
op in plain English + stating the scale (rows in, rows out, expected
runtime). Every write is followed by a `COUNT(*)` + `LIMIT 5` so the
participant sees the artifact (rules 3, 4, 6).

### Phase 6 — Verification & Reconciliation

Use `execute_query_tool` to verify every table (`COUNT(*)` + `LIMIT 5`).
If notebook generation drifted from the original design (renamed tables,
dropped columns), update the docs to match.

Onboard: the summary shows row counts per table next to what the design
promised, so the participant can see the design-to-data contract held
(rule 6).

---

## Gold scoring framework

Applied in Gold for each industry:

1. **Select** — pick industry-specific source metrics per hazard factor
   (see `./references/gold-scoring.md` for the full aspect-column table).
2. **Normalize** — min-max to [0,1], clamp, NULL→0, handle `min==max`.
   Normalize the *superset* of source columns used across industries in
   one pass, producing `norm_*` columns.
3. **Weight** — per-industry factor weights must sum to exactly 1.0.
4. **Classify** — **quantile-based** tiers via `percent_rank()`. Do NOT
   use fixed score thresholds (e.g., `score >= 0.8`) — with right-skewed
   hazard data they produce extreme imbalance. Full code example in
   `./references/gold-scoring.md`.
5. **Derive** — industry-specific business metrics (2–4 per industry).

Scoring is AOI-relative — not comparable across AOIs.

**Different industries must use different source columns** (not just
different weights). Same 3 columns × different weights produces nearly
identical tier distributions — visually useless. See `gold-scoring.md`
for the `INDUSTRY_FACTORS` pattern.

**Score explanation JSON**: every Gold row carries a `score_explanation`
STRING column with factor values, weights, AND source column names — so
downstream consumers (Felt, psycopg2 queries) can tell which raw column
drove each factor. See `gold-scoring.md` for the `to_json(struct(...))`
pattern.

---

## Non-obvious rules that apply on every generation

Use `search_documentation` MCP tool for general API reference; this
table covers only the non-obvious traps LLMs consistently hit.

| Rule | Wrong | Right |
|------|-------|-------|
| Session variable | `spark.read`, `spark.sql` | `sedona.read`, `sedona.sql` (after `SedonaContext.create()`) |
| Point arg order | `ST_Point(lat, lon)` | `ST_Point(lon, lat)` — X, Y |
| Geodesic distance | `ST_Distance` (returns degrees) | `ST_DistanceSpheroid` (returns meters) |
| KNN on EPSG:4326 points | `ST_KNN(a.geom, b.geom, k, FALSE, radius)` | `ST_KNN(a.geom, b.geom, k, TRUE, radius_m)` — **`use_sphere=TRUE` is mandatory** for lat/lon; without it `radius` is in degrees and results are meaningless |
| Raster CRS | `RS_SetSRID(raster, 4326)` regardless of source | Sedona auto-detects CRS from GeoTIFF metadata. Document source CRS in a `crs` STRING column. Only call `RS_SetSRID` when source truly lacks embedded CRS (rare). |
| Cross-CRS raster↔vector ops | Manual `ST_Transform` to match CRSs | `RS_ZonalStats` / `RS_Intersects` auto-reproject in Sedona 0.12+ — no manual transform needed if both sides have a known CRS |
| Raster intersection | `RS_Intersects(geometry, raster)` | `RS_Intersects(raster, geometry)` — raster first |
| Zonal stats 3-arg | `RS_ZonalStats(raster, geom, 'mean', true)` | `RS_ZonalStats(raster, geom, 'mean')` — no 4th arg for single-band |
| Zonal stats 5-arg | `RS_ZonalStats(raster, geom, 'max')` for multi-band | `RS_ZonalStats(raster, geom, 1, 'max', true)` — band index + allTouched |
| Zonal stats aggregation | No GROUP BY → duplicate rows | `GROUP BY asset_id, geometry` (assets span tiles) |
| Sub-pixel footprints | `ST_Buffer(geometry, 30)` then zonal stats | Use `allTouched=true` (5th arg) — faster, no extra shuffle |
| Iceberg write | `df.write.format("iceberg").save()` | `df.writeTo("...").createOrReplace()` |
| Iceberg append in loop | `.createOrReplace()` each iteration (destroys previous) | First iteration `.createOrReplace()`, subsequent `.append()` |
| Iceberg read | `sedona.read.format("iceberg").load()` | `sedona.table("catalog.db.table")` |
| S3 anonymous creds | Global anonymous provider | Per-bucket: `fs.s3a.bucket.<NAME>.aws.credentials.provider` |
| Missing data | `df.fillna(0)` | Keep NULLs + `has_<source>_data` flags |
| Snapshot cleanup | None after `createOrReplace` | `expire_snapshots(retain_last => 1)` |
| Weekly/temporal in enriched | LEFT JOIN weekly rows onto asset_enriched | Keep weekly table separate; aggregate in Gold before joining |
| Same factors all industries | Same 3 source columns, different weights | Different source columns per industry via `INDUSTRY_FACTORS` |
| Fixed tier thresholds | `Critical≥0.80, High≥0.60` | `percent_rank()` with percentile cuts — immune to score skew |
| Temporal windows | Single `WINDOW_START/END` for all sources | Per-source windows: `FLOOD_WINDOW_*`, `WEATHER_WINDOW_*` |
| Config cell edits | Partial updates that truncate existing vars | Always read the full cell, preserve every variable |

---

## Notebook conventions

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
**AOI filter at Bronze or Silver?** Silver. Bronze only if the full extent is impractical.

**Config cell safety**: when editing the config cell, always read the full
cell first and verify that ALL existing variables (`SCORING_WEIGHTS`,
`RISK_PERCENTILES`, `INDUSTRY_FACTORS`, `AURORA_SCHEMA`, etc.) survive.
Partial edits that truncate the cell are a common failure mode.

### ipynb format

Valid JSON: `nbformat: 4`, `nbformat_minor: 5`. Each source line ends
with `\n`. Code cells: `"outputs": [], "execution_count": null`. Markdown
cells: no outputs field.
