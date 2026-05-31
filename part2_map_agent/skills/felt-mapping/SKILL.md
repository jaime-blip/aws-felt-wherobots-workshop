---
name: felt-mapping
description: Create interactive Felt maps using the Felt MCP tools. Covers map creation, SQL-backed layers from Aurora PostgreSQL, FSL styling via generate_fsl, and layer management.
allowed-tools: list_data_sources create_map create_layer_from_data_source poll_layer_processing_status generate_fsl update_layer_properties render_map get_tabular_data_from_data_source
---

# Felt Mapping Skill (MCP)

Create interactive web maps using the Felt MCP tools directly.

## Available MCP Tools

| Tool | Purpose |
|------|---------|
| `list_data_sources` | Find connected database source IDs (look for PostgreSQL) |
| `create_map` | Create a new map with title, center, zoom, basemap |
| `create_layer_from_data_source` | Add a layer via SQL query against Aurora |
| `get_tabular_data_from_data_source` | Query data without creating a layer (for exploration) |
| `poll_layer_processing_status` | Wait for layer processing to complete |
| `generate_fsl` | AI-powered FSL style generation |
| `update_layer_properties` | Apply FSL style, rename layer, set caption |
| `render_map` | Show inline preview (call LAST after all edits) |

## Standard Workflow

### 1. Find the Data Source

```
Call: list_data_sources
Returns: List of connected databases — find the PostgreSQL one (usually "workshop-db")
Save: data_source_id for subsequent calls
```

### 2. Create a Map

```
Call: create_map
Parameters:
  - title: "My Map Title"
  - latitude: 32.7157  (San Diego center)
  - longitude: -117.1611
  - zoom: 10
  - basemap: "light" (or "dark", "satellite", "default")
Returns: map_id, url
```

### 3. Add a SQL Layer

```
Call: create_layer_from_data_source
Parameters:
  - map_id: <from step 2>
  - data_source_id: <from step 1>
  - sql_query: "SELECT * FROM workshop.insurance_exposure WHERE risk_tier = 'elevated' LIMIT 10000"
  - name: "Elevated Risk Buildings"
Returns: layer_id
```

**SQL Requirements:**
- ALWAYS use `workshop.` schema prefix
- ALWAYS include geometry column
- Use LIMIT (max 100,000 rows)

### 4. Wait for Processing

```
Call: poll_layer_processing_status
Parameters:
  - map_id: <from step 2>
  - layer_id: <from step 3>
  - wait_seconds: 30
Returns: status ("completed" or "in_progress" or "failed")
```

Repeat until status is "completed".

### 5. Generate Style

```
Call: generate_fsl
Parameters:
  - map_id: <from step 2>
  - layer_id: <from step 3>
  - geometry_type: "polygon" (or "point", "line")
  - description: "Categorical coloring by risk_tier. Orange for elevated, red for high, dark red for critical. Include popup with risk_score."
Returns: FSL style object
```

The `generate_fsl` tool inspects the layer's actual data to make informed styling decisions.

### 6. Apply Style

```
Call: update_layer_properties
Parameters:
  - map_id: <from step 2>
  - layer_id: <from step 3>
  - style: <FSL from step 5>
  - name: "Risk Buildings" (optional rename)
  - caption: "Colored by risk tier" (optional)
```

### 7. Render Map

```
Call: render_map
Parameters:
  - map_id: <from step 2>
Returns: Inline preview widget + URL
```

**IMPORTANT:** Call `render_map` as the LAST step. It captures a snapshot at the moment of the call.

## Multi-Layer Maps

Add layers one at a time, waiting for each to complete:

1. Create map
2. Add layer 1 → poll → style
3. Add layer 2 → poll → style
4. Render map (once, at the end)

## Zoom-Aware Styling (size / opacity ramps)

Any numeric paint property can interpolate across zoom levels using
`{"linear": [[zoom, value], [zoom, value], ...]}`. Plus `minZoom` / `maxZoom`
in `paint` clamp where a layer draws. This all lives in FSL — there is no
separate "layer visibility" API, so use opacity ramps to show/hide by zoom.

```json
"size":    {"linear": [[5, 4], [15, 12]]}
"opacity": {"linear": [[10, 0.9], [13, 0]]}
```

## Pattern: Risk-density heatmap that resolves into features (overview → detail)

A high-impact two-layer map: a glowing **H3 hexbin** heatmap when zoomed out,
the **individual features** when zoomed in, cross-faded purely by style. Great
for dense point/polygon sets (e.g. tens of thousands of buildings) that turn to
dot-mush at low zoom.

1. **Dark basemap** so the heat glows: `update_map` with `basemap: "dark"`.
2. **Overview layer — H3 hexbins.** H3 bins by *point* location, so query
   **centroids** of the features plus the metric to aggregate:
   ```sql
   SELECT asset_id, risk_score, ST_Centroid(geometry) AS geometry
   FROM workshop.insurance_exposure WHERE risk_tier IN ('high','critical')
   ```
   Style (`generate_fsl` viz_type `h3`, then add the fade-out ramp):
   ```json
   {"type": "h3", "version": "2.3.1",
    "config": {"numericAttribute": "risk_score", "aggregation": "mean",
               "baseBinLevel": 7, "binMode": "high",
               "steps": {"type": "quantiles", "count": 5}},
    "paint":  {"color": "@ylRed", "opacity": {"linear": [[10, 0.9], [13, 0]]},
               "strokeColor": "#1a0000", "strokeWidth": 0.5}}
   ```
   `aggregation` accepts `mean` (avg), `sum`, `count`, `min`, `max`.
   `binMode: "high"` + higher `baseBinLevel` (7) = finer hotspots.
3. **Detail layer — the features themselves** (polygons), categorical by tier,
   with the mirror fade-*in* ramp so they appear as the heatmap fades:
   ```json
   "opacity": {"linear": [[11, 0], [13, 0.85]]}
   ```
4. Poll both, then `render_map`. Crossover lands around z12; widen the band
   (e.g. `[[10,…],[14,…]]`) for a softer dissolve.

## Buffer / Reference Layers

To add a buffer circle around a point, use PostGIS in the SQL query:

```sql
SELECT
    'Downtown 10-mile buffer' as name,
    ST_Buffer(
        ST_SetSRID(ST_MakePoint(-117.1611, 32.7157), 4326)::geography,
        16093.44  -- 10 miles in meters
    )::geometry as geometry
```

Then style with:
```
generate_fsl description: "Transparent fill with blue stroke outline. No fill color, just the boundary."
```

**Common buffer distances:**
| Miles | Meters |
|-------|--------|
| 5 | 8046.72 |
| 10 | 16093.44 |
| 20 | 32186.88 |

## Styling Descriptions for generate_fsl

The `generate_fsl` tool takes a natural language description. Examples:

**Categorical:**
- "Categorical coloring by risk_tier. Orange for elevated, red for high, dark red for critical."
- "Color by building_class using a qualitative palette."

**Numeric:**
- "Gradient from green (low) to red (high) based on risk_score."
- "Heat gradient by wildfire_factor."

**Simple:**
- "All features in blue with 50% opacity."
- "Transparent fill with dark blue stroke."

**With popups:**
- "...Include popup showing asset_id, risk_tier, and risk_score."

## Querying Without Creating Layers

To explore data before mapping:

```
Call: get_tabular_data_from_data_source
Parameters:
  - map_id: <any map you have access to>
  - data_source_id: <from list_data_sources>
  - sql_query: "SELECT risk_tier, COUNT(*) FROM workshop.insurance_exposure GROUP BY risk_tier"
Returns: Tabular results (not a layer)
```

## Common Gotchas

1. **Always find data_source_id first** — don't guess or hardcode
2. **Always poll after adding layers** — styling a processing layer will fail
3. **Always render last** — it's a snapshot, not a live view
4. **Use generate_fsl** — don't hand-write FSL, the tool does it better
5. **Include geometry in SQL** — layers need a geometry column
6. **Use workshop. prefix** — bare table names fail
