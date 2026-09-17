# Geospatial Risk Intelligence — Data Dictionary

> Medallion Architecture: Bronze → Silver → Gold
>
> This document describes every table in the pipeline, the data sources that feed them,
> and the business logic used to derive each metric.

---

## Architecture Overview

```
Bronze (Raw Sources)          Silver (Enriched)                Gold (Industry-Scored)
─────────────────────         ──────────────────               ──────────────────────
Overture Buildings    ──┐
                        ├──▶ asset_wildfire_exposure ──┐
USFS Burn Probability ──┤                              │
USFS Flame Length     ──┘                              │
                                                       ├──▶ asset_enriched ──▶ insurance_exposure
OPERA DSWx-S1         ────▶ asset_flood_exposure    ──┤                   ──▶ cre_risk
                                                       │                   ──▶ capital_markets_signals
NOAA SWDI Hail        ──┐                              │                   ──▶ energy_asset_risk
NOAA SWDI Structure   ──┼──▶ asset_weather_density  ──┘
NOAA SWDI TVS         ──┘
```

---

## Bronze Layer — Raw Data Sources

These are catalog-registered datasets consumed directly from Wherobots Open Data and org_catalog. No transformations are applied at this layer.

| Source | Catalog Table | Type | Description |
|---|---|---|---|
| Overture Buildings | `wherobots_open_data.overture_maps_foundation.buildings_building` | Vector | Global building footprints with height, floor count, class, and subtype |
| USFS Burn Probability | `org_catalog.wildfire_risk.burn_probability_conus` | Raster | CONUS-wide burn probability grids from USFS (annual probability a pixel burns) |
| USFS Conditional Flame Length | `org_catalog.wildfire_risk.conditional_flame_length_conus` | Raster | CONUS-wide conditional flame length grids from USFS (expected flame length if fire occurs) |
| OPERA DSWx-S1 | `org_catalog.opera.dswx_s1` | Raster | Sentinel-1 SAR-derived surface water / flood classification (30 m, per-acquisition) |
| NOAA SWDI — Hail | `org_catalog.noaa_swdi.hail` | Vector | Hail event reports with severity probability and max hail size |
| NOAA SWDI — Mesocyclone Structures | `org_catalog.noaa_swdi.structure` | Vector | Mesocyclone structure detections with max reflectivity and VIL |
| NOAA SWDI — TVS | `org_catalog.noaa_swdi.tvs` | Vector | Tornado Vortex Signature detections with max delta velocity and max shear |

### Scope Filters Applied at Ingestion

- **Geographic**: All sources are clipped to the Area of Interest (AOI) polygon using `ST_Intersects` (vector) or `RS_Intersects` (raster)
- **Temporal**: Each source is filtered to its own window — NOAA SWDI to `WEATHER_WINDOW_START/END`, OPERA DSWx-S1 to `FLOOD_WINDOW_START/END`. Wildfire rasters are a single CONUS snapshot (no temporal filter).

---

## Silver Layer — Spatially Enriched Tables

Each Silver table joins building footprints with one hazard source to produce per-asset exposure metrics. All tables are written to Apache Iceberg under `org_catalog.silver`.

### `asset_wildfire_exposure`

Per-building wildfire risk derived from USFS raster data via zonal statistics.

| Column | Description |
|---|---|
| `asset_id` | Overture building ID |
| `asset_type` | Always `building` |
| `geometry` | Building footprint polygon |
| `height` | Building height (meters) |
| `num_floors` | Number of floors |
| `class` | Overture building class |
| `burn_prob_mean` | Mean burn probability across all raster tiles overlapping the footprint |
| `burn_prob_max` | Maximum burn probability across overlapping tiles |
| `flame_length_mean` | Mean conditional flame length (feet) across overlapping tiles |
| `wildfire_risk_class` | Categorical tier based on `burn_prob_mean` |
| `computed_at` | Processing timestamp |

**How it's computed**: Building footprints are spatially joined to burn probability raster tiles using `RS_Intersects`. For each building, `RS_ZonalStats(raster, geometry, 'mean')` and `RS_ZonalStats(raster, geometry, 'max')` extract the mean and max burn probability. The same approach is used for flame length with a separate raster layer. Results are aggregated per building (a building may overlap multiple tiles).

**Wildfire risk classification thresholds** (based on `burn_prob_mean`):

| Tier | Threshold |
|---|---|
| Extreme | ≥ 0.05 |
| Very High | ≥ 0.01 |
| High | ≥ 0.002 |
| Moderate | ≥ 0.0005 |
| Low | < 0.0005 |

---

### `asset_flood_exposure`

Per-building, **per-ISO-week** flood exposure derived from OPERA DSWx-S1 SAR flood/water-classification rasters via weekly zonal statistics. One row per `(asset_id, flood_week)` pair — `silver-to-gold` aggregates these to a single row per asset at read time.

| Column | Description |
|---|---|
| `asset_id` | Overture building ID |
| `asset_type` | Always `building` |
| `geometry` | Building footprint polygon |
| `flood_week` | Monday-aligned ISO week start date for this observation |
| `flood_max_wtr_class` | Max OPERA water classification observed that week (0=dry, 1=open water, 2=partial surface water) |
| `observation_window_start` | `FLOOD_WINDOW_START` — pipeline parameter |
| `observation_window_end` | `FLOOD_WINDOW_END` — pipeline parameter |
| `computed_at` | Processing timestamp |

**How it's computed**: For each ISO week in `FLOOD_WINDOW_START → FLOOD_WINDOW_END`, the B01_WTR band tiles falling in that week are intersected with building footprints. `RS_ZonalStats(raster, geometry, 'max', allTouched=true)` extracts the peak water-classification value per building-week. Processing week-by-week keeps shuffle size small (buildings × 1 week of raster) and provides checkpointing — if a week fails, earlier weeks are already in Iceberg.

---

### `asset_weather_density`

Per-building severe weather proximity and density derived from NOAA SWDI via KNN spatial join.

| Column | Description |
|---|---|
| `asset_id` | Overture building ID |
| `asset_type` | Always `building` |
| `geometry` | Building footprint polygon |
| `event_count_5km` | Total severe weather events within 5 km |
| `event_count_25km` | Total severe weather events within 25 km |
| `nearest_event_dist_m` | Distance to the single nearest event of any type (meters) |
| `nearest_hail_m` | Distance to the nearest hail event (meters) |
| `nearest_structure_m` | Distance to the nearest mesocyclone structure event (meters) |
| `nearest_tvs_m` | Distance to the nearest TVS event (meters) |
| `hail_count_25km` | Hail events within 25 km |
| `structure_count_25km` | Mesocyclone structure events within 25 km |
| `tvs_count_25km` | TVS events within 25 km |
| `max_severity` | Maximum severity value across all matched events |
| `observation_window_start` | `WEATHER_WINDOW_START` — pipeline parameter |
| `observation_window_end` | `WEATHER_WINDOW_END` — pipeline parameter |
| `computed_at` | Processing timestamp |

**How it's computed**: For each of the three SWDI event types (hail, structure, TVS), a KNN spatial join finds the 10 nearest events within a 25 km search radius using `ST_KNN(building, event, 10, true, 25000)`. The `use_sphere=true` parameter ensures all distances and the search radius are geodesic (meters). Exact distances are computed via `ST_DistanceSpheroid`. Per-event-type results are written to a staging table then aggregated per building — counting events at the 5 km and 25 km thresholds and recording the nearest distance per event type.

---

### `asset_enriched`

Unified Silver table that joins all three hazard exposure layers onto the full building set. This is the single input table for all Gold scoring.

| Column | Source |
|---|---|
| `asset_id`, `geometry`, `building_class`, `height`, `num_floors` | Overture Buildings |
| `burn_prob_mean`, `burn_prob_max`, `flame_length_mean`, `wildfire_risk_class` | `asset_wildfire_exposure` |
| `flood_max_wtr_class`, `flood_event_count`, `flood_duration_days` | `asset_flood_exposure` (aggregated from weekly rows in `silver-to-gold`) |
| `event_count_5km`, `event_count_25km`, `nearest_event_dist_m`, `nearest_hail_m`, `nearest_structure_m`, `nearest_tvs_m`, `hail_count_25km`, `structure_count_25km`, `tvs_count_25km`, `max_severity` | `asset_weather_density` |
| `weather_window_start`, `weather_window_end` | Pipeline configuration (SWDI window) |

**How it's computed**: LEFT JOIN from the full AOI buildings table to each of the three Silver hazard tables on `asset_id`. Every building appears in the output; hazard columns are null if the building had no exposure in that layer.

---

## Gold Layer — Industry-Specific Risk Scores

All Gold tables start from `asset_enriched` and apply the same normalization and scoring framework, then add industry-specific derived metrics. Each table is written to Iceberg (`org_catalog.gold`) and GeoParquet on S3.

### Shared Scoring Framework

**Normalization**: Each raw hazard metric is normalized to [0, 1] using min-max scaling across all assets:

| Factor | Source Column |
|---|---|
| `wildfire_factor` | `burn_prob_mean` |
| `flood_factor` | `flood_max_extent` |
| `severe_weather_factor` | `event_count_25km` |

**Composite Risk Score**: Weighted sum of the three normalized factors. Weights vary by industry (see table below) and always sum to 1.0.

| Industry | Wildfire | Flood | Severe Weather |
|---|---|---|---|
| Insurance | 0.40 | 0.40 | 0.20 |
| Commercial Real Estate | 0.30 | 0.35 | 0.35 |
| Capital Markets | 0.20 | 0.30 | 0.50 |
| Energy & Utilities | 0.40 | 0.20 | 0.40 |

**Risk Tiers** (applied uniformly to the composite risk score):

| Tier | Score Range |
|---|---|
| Critical | ≥ 0.80 |
| High | 0.60 – 0.79 |
| Elevated | 0.40 – 0.59 |
| Moderate | 0.20 – 0.39 |
| Low | < 0.20 |

---

### `insurance_exposure`

Target audience: Insurance underwriters, CAT modelers, portfolio managers.

| Column | Description |
|---|---|
| `asset_id`, `geometry`, `building_class` | Asset identifiers |
| `wildfire_factor`, `flood_factor`, `severe_weather_factor` | Normalized [0–1] hazard factors |
| `risk_score` | Weighted composite (wf 0.40, fl 0.40, sw 0.20) |
| `risk_tier` | Categorical tier from risk_score |
| `exposure_delta` | Change in risk score vs. baseline period |
| `triage_priority` | Global rank ordering by exposure_delta (1 = highest urgency) |
| `estimated_loss_band` | Heuristic loss estimate bucket |
| `score_explanation` | JSON breakdown of factor weights and values |

**Business logic**:
- `exposure_delta` = `risk_score` minus baseline risk score (compares event-window conditions to pre-event baseline)
- `triage_priority` = `ROW_NUMBER()` ordered by `exposure_delta` descending, so the asset with the largest risk increase is ranked #1
- `estimated_loss_band` assigns a dollar-range bucket based on risk_score: ≥0.80 → ">$1M", ≥0.60 → "$250K–$1M", ≥0.30 → "$50K–$250K", otherwise "<$50K"

---

### `cre_risk`

Target audience: CRE acquisition analysts, asset managers, environmental risk teams.

| Column | Description |
|---|---|
| `asset_id`, `geometry`, `building_class` | Asset identifiers |
| `wildfire_factor`, `flood_factor`, `severe_weather_factor` | Normalized [0–1] hazard factors |
| `risk_score` | Weighted composite (wf 0.30, fl 0.35, sw 0.35) |
| `risk_tier` | Categorical tier from risk_score |
| `acquisition_screen_flag` | Boolean — true if risk_score ≥ 0.60 |
| `environmental_risk_index` | Risk score adjusted by building size |
| `hazard_proximity_m` | Distance to nearest severe weather event (meters) |
| `score_explanation` | JSON breakdown of factor weights and values |

**Business logic**:
- `acquisition_screen_flag` = true when `risk_score ≥ 0.60` — flags assets that require environmental due diligence before acquisition
- `environmental_risk_index` = `risk_score × log(1 + num_floors)` — amplifies risk for taller buildings (more value at risk)
- `hazard_proximity_m` = geodesic distance in meters to the nearest severe weather event (-1 if no event data)

---

### `capital_markets_signals`

Target audience: Quantitative analysts, equity researchers, supply chain risk teams.

| Column | Description |
|---|---|
| `asset_id`, `geometry`, `building_class` | Asset identifiers |
| `wildfire_factor`, `flood_factor`, `severe_weather_factor` | Normalized [0–1] hazard factors |
| `risk_score` | Weighted composite (wf 0.20, fl 0.30, sw 0.50) |
| `risk_tier` | Percentile-rank tier: critical / high / elevated / moderate / low (same rule as the other Gold tables) |
| `disruption_signal` | Relative likelihood of a facility going offline (ranking signal, not a calibrated probability) |
| `supply_chain_vulnerability` | Proximity-weighted risk index, bounded [0, 1] |
| `event_density_signal` | Geometric mean of the severe weather factor and proximity |
| `score_explanation` | JSON breakdown of factor weights and values |

**Business logic**:
- `disruption_signal` = sigmoid function: `1 / (1 + e^(-10 × (risk_score - 0.5)))` — maps the linear risk score to an S-curve centered at 0.5
- `supply_chain_vulnerability` = `min(1, 1 / log(1 + nearest_event_km))` — inverse-log distance weighting where closer events produce higher vulnerability; uses geodesic distance converted from meters to km
- `event_density_signal` = `sqrt(severe_weather_factor × supply_chain_vulnerability)`

---

### `energy_asset_risk`

Target audience: Utility grid planners, pipeline operators, energy reliability teams.

| Column | Description |
|---|---|
| `asset_id`, `geometry`, `building_class` | Asset identifiers |
| `wildfire_factor`, `flood_factor`, `severe_weather_factor` | Normalized [0–1] hazard factors |
| `risk_score` | Weighted composite (wf 0.40, fl 0.20, sw 0.40) |
| `risk_tier` | Categorical tier from risk_score |
| `outage_probability` | Modeled outage likelihood |
| `vegetation_encroachment_risk` | Wildfire-driven vegetation threat level |
| `weather_impact_frequency` | Annualized severe weather event rate |
| `score_explanation` | JSON breakdown of factor weights and values |

**Business logic**:
- `outage_probability` = `1 - (1 - wildfire_factor × 0.5)^(1 + event_count_5km)` — models cumulative outage risk where each nearby severe weather event compounds the base wildfire-driven outage probability
- `vegetation_encroachment_risk` = `burn_prob_mean × multiplier` — the raw burn probability scaled by 1.5× for assets in extreme/very_high/high wildfire risk classes to reflect elevated vegetation-fire interaction
- `weather_impact_frequency` = `event_count_25km / observation_years` — annualized count of severe weather events within 25 km, computed over the full observation window

---

## Output Destinations

Each Gold table is written to three destinations:

| Destination | Format | Path / Location |
|---|---|---|
| Wherobots Iceberg | Apache Iceberg | `org_catalog.gold.<table_name>` |
| S3 GeoParquet (optional) | GeoParquet | `GEOPARQUET_BASE/<table_name>` — off by default; set `GEOPARQUET_BASE` in the silver-to-gold config cell to a folder in your org's Wherobots managed storage to enable |
| Aurora PostgreSQL | JDBC / PostGIS | `workshop.<table_name>` (geometries stored as WKT) |
