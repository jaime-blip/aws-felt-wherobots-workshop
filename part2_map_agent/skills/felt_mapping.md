# Felt Mapping Skill

Create interactive maps from any database table using the Felt API.

## Setup

```python
import os
os.environ["FELT_API_TOKEN"] = os.environ.get("FELT_API_TOKEN", "")
from felt_python import create_map, add_source_layer, list_layers, update_layer_style
```

## Create a Map

```python
response = create_map(title="My Map", lat=30.27, lon=-97.74, zoom=11)
map_id = response["id"]
map_url = response["url"]
```

## Add Data from Source

Our PostgreSQL source ID: **`SUdIQGqeTFKqkHrx9AYVPDA`**

### Add layer via SQL query (preferred):
```python
import time
add_source_layer(
    map_id=map_id,
    source_layer_params={
        "from": "sql",
        "source_id": "SUdIQGqeTFKqkHrx9AYVPDA",
        "query": "SELECT * FROM schema.table WHERE ..."
    }
)
time.sleep(3)
layers = list_layers(map_id=map_id)
layer_id = layers[-1]["id"]
```

**SQL rules:**
- Must include a geometry column
- Geometry must be SRID 4326 (or use ST_Transform)
- Read-only SELECT queries only
- Use schema-qualified names (e.g., `public.building_risk`, `real_estate.past_sales`)

## Style Layers with FSL

**CRITICAL FORMAT:** Categories are plain strings. Colors are a parallel array in `paint.color`.

### Categorical (for TEXT columns):
```python
style = {
    "version": "2.3.1",
    "type": "categorical",
    "config": {
        "labelAttribute": ["column_name"],
        "categories": ["value1", "value2", "value3"]
    },
    "paint": {
        "color": ["#DC2626", "#F97316", "#22C55E"],
        "size": 8,
        "strokeWidth": 1,
        "strokeColor": "#ffffff",
        "opacity": 0.9
    },
    "legend": {}
}
update_layer_style(map_id=map_id, layer_id=layer_id, style=style)
```

### Numeric gradient (for FLOAT/INT columns):
```python
style = {
    "version": "2.3.1",
    "type": "numeric",
    "config": {
        "numericAttribute": "column_name",
        "steps": 5
    },
    "paint": {
        "color": ["#22C55E", "#84CC16", "#EAB308", "#F97316", "#DC2626"],
        "size": 8
    },
    "legend": {}
}
```

### Simple (single color, no classification):
```python
style = {
    "version": "2.3.1",
    "type": "simple",
    "paint": {
        "color": "#3B82F6",
        "size": 8,
        "strokeWidth": 1,
        "strokeColor": "#ffffff",
        "opacity": 0.9
    },
    "legend": {}
}
```

## Color Palettes

**Risk/diverging:** `["#22C55E", "#84CC16", "#EAB308", "#F97316", "#DC2626"]` (green→red)
**Cool:** `["#E0F2FE", "#7DD3FC", "#38BDF8", "#0284C7", "#075985"]` (light→dark blue)
**Warm:** `["#FEF3C7", "#FCD34D", "#F59E0B", "#D97706", "#92400E"]` (yellow→brown)
**Qualitative:** `["#3B82F6", "#EF4444", "#22C55E", "#F59E0B", "#8B5CF6", "#EC4899"]`

## Workflow

1. **Discover** — Query Aurora to understand the table (columns, types, distinct values)
2. **Decide** — Pick the right style type: categorical for text, numeric for numbers
3. **Create map** — Center it on the data's geographic extent
4. **Add layer** — SQL source layer with relevant columns and optional WHERE filter
5. **Style** — Apply FSL based on the most interesting attribute
6. **Share** — Print the map URL

## Tips
- ALWAYS print the Felt map URL at the end
- Use `list_layers()` after `add_source_layer()` to get the real layer_id (add a `time.sleep(3)`)
- To find the center of data: `SELECT AVG(ST_Y(geom)), AVG(ST_X(geom)) FROM table`
- Choose zoom: city=11, region=8, country=5
- When in doubt about column types, query the data first
