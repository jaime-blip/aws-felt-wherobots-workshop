# OPERA DSWx-S1 flood data — Bronze/Silver handling

Detailed reference for working with `org_catalog.opera.dswx_s1`. Load this
when generating the flood section of `bronze-to-silver.ipynb`, or when a
participant asks about flood data specifically.

The rules that matter on every spatial operation (auto-reproject,
`RS_ZonalStats` signatures, etc.) live in the main `SKILL.md`. This file
is the OPERA-specific material.

---

## Band layout

OPERA DSWx-S1 produces four co-registered GeoTIFFs per acquisition,
distinguished by filename suffix:

| Band suffix | Meaning | Use in Silver |
|---|---|---|
| `B01_WTR`  | Water classification (0=dry, 1=open water, 2=partial surface water) | **Primary** — use this for flood exposure |
| `B02_BWTR` | Binary water mask | Incremental signal beyond B01; rarely needed |
| `B03_CONF` | Classification confidence | Confidence-weighting variant only |
| `B04_DIAG` | Diagnostic layer | Debugging / QA — do not ingest into Silver |

**Default**: filter to `band = 'B01_WTR'` in the Silver ingest. Loading all
four bands quadruples the work with marginal value for most workflows.
Only load additional bands if the participant explicitly asks for
confidence weighting.

## CRS

**EPSG:32611** (UTM Zone 11N) — correct for the San Diego reference AOI.
For other AOIs, verify via `describe_table` + `RS_Metadata(raster)` since
OPERA tiles are UTM-zoned by MGRS grid (Zone 11 for California, Zone 17
for Florida, etc.).

Sedona 0.12+ auto-reprojects in `RS_ZonalStats` and `RS_Intersects`, so
the mismatch with the EPSG:4326 building footprints is handled
automatically — do not call `ST_Transform`.

## Temporal filter

Always filter by acquisition date AND band:

```sql
WHERE acq_date BETWEEN DATE('{FLOOD_WINDOW_START}')
                   AND DATE('{FLOOD_WINDOW_END}')
  AND band = 'B01_WTR'
```

The `FLOOD_WINDOW_START`/`FLOOD_WINDOW_END` are pipeline parameters (see
SKILL.md on per-source windows). For the reference pipeline: Dec 2025 →
Mar 2026.

## Weekly granularity

OPERA acquisitions happen ~every 6–12 days per MGRS tile, which makes
"flood observations at a building" noisy at acquisition granularity. Bin
to ISO weeks so each (asset, week) row is one observation:

- One row per `(asset_id, flood_week)`
- `flood_week` is the Monday-aligned ISO week start date
- `flood_max_wtr_class` is the peak WTR value observed that week

This keeps the temporal signal while cutting row count by roughly 3×
vs per-acquisition rows.

## Week-by-week Iceberg append loop

For large flood datasets, processing all weeks in one Spark job causes
excessive shuffle (buildings × all-tiles-in-window). Iterate week by
week — each iteration processes `buildings × one week of tiles`:

```python
from datetime import date, timedelta

start = date.fromisoformat(FLOOD_WINDOW_START)
end   = date.fromisoformat(FLOOD_WINDOW_END)

# Align to Monday, step by 7 days
week_start = start - timedelta(days=start.weekday())
weeks = []
while week_start <= end:
    weeks.append(week_start)
    week_start += timedelta(days=7)

FLOOD_SILVER = f"org_catalog.{SILVER_DB}.asset_flood_exposure"

for i, wk in enumerate(weeks):
    wk_end = wk + timedelta(days=6)
    wk_start_clamped = max(wk, start)
    wk_end_clamped   = min(wk_end, end)

    df = sedona.sql(f"""
        SELECT
            b.id                                                        AS asset_id,
            b.geometry,
            DATE('{wk.isoformat()}')                                    AS flood_week,
            MAX(RS_ZonalStats(w.raster, b.geometry, 1, 'max', true))    AS flood_max_wtr_class
        FROM buildings b
        JOIN flood_b01_wtr w
            ON RS_Intersects(w.raster, b.geometry)
        WHERE w.acq_date BETWEEN DATE('{wk_start_clamped.isoformat()}')
                              AND DATE('{wk_end_clamped.isoformat()}')
        GROUP BY b.id, b.geometry
    """)

    if i == 0:
        df.writeTo(FLOOD_SILVER).createOrReplace()
    else:
        df.writeTo(FLOOD_SILVER).append()
```

Two invariants of this pattern:
1. **First iteration** uses `createOrReplace()` (idempotent table seed).
2. **Subsequent iterations** use `append()` — never `createOrReplace()`
   inside the loop, or each iteration destroys the previous.

## Flood metrics available for Gold

After the weekly silver table is written, Gold aggregates it per asset.
The three metrics that come out of that aggregation, and what each
captures:

| Metric | SQL | What it captures |
|---|---|---|
| `flood_event_count`   | `SUM(CASE WHEN flood_max_wtr_class >= 1 THEN 1 ELSE 0 END)` | Frequency — number of weeks with any water |
| `flood_duration_days` | `DATEDIFF(MAX(flood_week), MIN(flood_week))` | Duration — span between first and last flood |
| `flood_max_wtr_class` | `MAX(flood_max_wtr_class)` | Severity — peak water class seen |

Different industries pick different metrics — see `gold-scoring.md` for
the per-industry mapping.

## Deferred join — asset_flood_exposure is NOT joined into asset_enriched

Because `asset_flood_exposure` has multiple rows per asset (one per week),
it breaks the 1:1 guarantee of `asset_enriched`. The pattern is:

1. Silver writes `asset_flood_exposure` as the weekly table.
2. `asset_enriched` LEFT JOINs wildfire + weather only (both 1:1).
3. Gold loads `asset_flood_exposure`, aggregates to per-asset using the
   SQL above, then LEFT JOINs those aggregates onto `asset_enriched`.

This is a non-obvious rule — the main SKILL.md calls it out in the
gotchas table, and the per-layer contracts live in `medallion-spec.md`.
