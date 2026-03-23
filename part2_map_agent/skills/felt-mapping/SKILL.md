---
name: felt-mapping
description: Create interactive Felt maps from spatial data. Covers map creation, SQL source layers from PostgreSQL, FSL styling (categorical, numeric, heatmaps, icons, labels), layer polling, and map verification. Use when building or styling Felt maps.
allowed-tools: python_repl file_read
---

# Felt Mapping Skill

Create interactive web maps using the `felt-python` library and FSL (Felt Style Language).

For the full API reference, see [references/FULL_REFERENCE.md](references/FULL_REFERENCE.md).

## Key Concepts

- **Source layers**: Connect to a PostgreSQL database and query data via SQL
- **FSL (Felt Style Language)**: JSON-based styling (categorical, numeric, heatmap, icons, labels)
- **Polling**: Layers process asynchronously — MUST wait for `completed` before styling

## Environment

```python
# Pre-loaded in python_repl:
TOKEN = os.environ["FELT_API_TOKEN"]
SOURCE_ID = os.environ["FELT_SOURCE_ID"]

# felt_python functions (always pass api_token=TOKEN):
from felt_python import create_map, add_source_layer, list_layers, update_layer_style

# Helper functions:
from felt_helpers import wait_for_layer, categorical_style, numeric_style
```

## Workflow

### 1. Create a Map

```python
m = create_map(title="My Map", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]
print(f"Map: {map_url}")
```

### 2. Add a SQL Source Layer

```python
params = {
    "from": "sql",
    "source_id": SOURCE_ID,
    "query": "SELECT * FROM public.my_table"
}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)
```

### 3. Wait for Processing (MANDATORY)

```python
layer = wait_for_layer(map_id)  # polls every 3s until completed
layer_id = layer["id"]
```

- Statuses: `processing` → `completed` (or `failed`)
- Small tables: ~6-9s. Large tables (1000+): 15-30s
- **Never style before `completed`** — you'll get 422 errors

### 4. Apply FSL Style

```python
# Categorical (text column)
style = categorical_style("my_column", top_n=10)
update_layer_style(map_id=map_id, layer_id=layer_id, style=style, api_token=TOKEN)

# Numeric (number column)
style = numeric_style("my_number_column", palette="@ylRed")
update_layer_style(map_id=map_id, layer_id=layer_id, style=style, api_token=TOKEN)
```

### 5. Verify

```python
import urllib.request, json
req = urllib.request.Request(
    f"https://felt.com/api/v2/maps/{map_id}/layers",
    headers={"Authorization": f"Bearer {TOKEN}"}
)
layers = json.loads(urllib.request.urlopen(req).read())
for layer in layers:
    print(f"  {layer['name']}: status={layer['status']}, features={layer.get('metadata',{}).get('feature_count','?')}")
```

## Multi-Layer Maps

Add layers one at a time. Style each before adding the next:

```python
for table, col in [("public.table1", "col1"), ("public.table2", "col2")]:
    params = {"from": "sql", "source_id": SOURCE_ID, "query": f"SELECT * FROM {table}"}
    add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)
    layer = wait_for_layer(map_id)
    update_layer_style(
        map_id=map_id, layer_id=layer["id"],
        style=categorical_style(col, top_n=10),
        api_token=TOKEN
    )
    print(f"  Added {table}")
```

## FSL Quick Reference

All FSL styles must include `"version": "2.3.1"`.

### Categorical Style

```json
{
    "version": "2.3.1",
    "type": "categorical",
    "config": {
        "categoricalAttribute": "column_name",
        "categories": {"type": "top", "count": 10},
        "showOther": true
    },
    "paint": {
        "color": "@catPalette4",
        "size": 6,
        "opacity": 0.9,
        "strokeColor": "auto",
        "strokeWidth": 1
    },
    "legend": {}
}
```

Or with explicit categories + colors:

```json
{
    "version": "2.3.1",
    "type": "categorical",
    "config": {
        "categoricalAttribute": "status",
        "categories": ["Active", "Contained", "Out"],
        "showOther": true
    },
    "paint": {
        "color": ["#e74c3c", "#f39c12", "#2ecc71"],
        "size": 6,
        "opacity": 0.9
    },
    "legend": {
        "displayName": {
            "Active": "Active Fire",
            "Contained": "Contained",
            "Out": "Extinguished"
        }
    }
}
```

### Numeric Style

```json
{
    "version": "2.3.1",
    "type": "numeric",
    "config": {
        "numericAttribute": "value",
        "steps": {"type": "jenks", "count": 5}
    },
    "paint": {
        "color": "@ylRed",
        "opacity": 0.8,
        "strokeColor": "auto"
    },
    "legend": {}
}
```

### Palette Shortcuts

- `@catPalette1` through `@catPalette5` — categorical
- `@ylRed`, `@galaxy`, `@buGn`, `@worb` — sequential/diverging
- `@fire`, `@ice` — thematic

### Common Gotchas

1. **`version: "2.3.1"` is required** — without it, 422 error
2. **`showOther` not `showUncategorized`** — wrong key = silent failure
3. **`legend.displayName` is a dict** `{"value": "Label"}` — not a string
4. **Categories are plain strings** — not objects with `{value, color}`
5. **Colors parallel to categories** — `paint.color` array must match `categories` array length
6. **Style endpoint is POST** — `update_layer_style()` handles this

## Additional References

For advanced styling (heatmaps, icons, labels, popups, filters, raster, MapLibre expressions),
see [references/FULL_REFERENCE.md](references/FULL_REFERENCE.md).
