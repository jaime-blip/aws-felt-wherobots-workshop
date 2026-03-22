# Workshop-Specific Notes (READ FIRST)

## Aurora PostgreSQL Source
- **Source ID:** `SUdIQGqeTFKqkHrx9AYVPDA`
- Use `add_source_layer()` with `"from": "sql"` and this source_id for all database queries
- **ALWAYS pass `api_token=token` to every felt_python function call**
- Get token with: `token = os.environ["FELT_API_TOKEN"]`
- Geometry column names vary (`geometry`, `geom`) — always discover first
- After `add_source_layer()`, **poll for processing completion** before styling:

```python
import time
from felt_python import list_layers

# MANDATORY: poll until layer processing is done
layer_id = None
for _ in range(20):  # up to ~60s
    time.sleep(3)
    layers = list_layers(map_id=map_id, api_token=token)
    if layers:
        status = layers[0].get("status")
        progress = layers[0].get("progress", 0)
        print(f"  Layer status: {status} ({progress}%)")
        if status == "completed":
            layer_id = layers[0]["id"]
            break
        if status == "failed":
            raise Exception("Layer processing failed!")

if not layer_id:
    raise Exception("Layer never finished processing")
```

- **Never style a layer before it reaches `status == "completed"`** — you'll get 422 errors
- Statuses: `processing` → `completed` (or `failed`). Progress: 0→100.
- Large tables (1000+ rows) may take 15-30s; small ones ~6-9s

---

---
name: felt
description: Skill for working with Felt web-based GIS software. Use this skill when the user wants to create maps, add GIS data layers, add annotations (elements), style map features, or work with the felt-python library and FSL (Felt Style Language). This skill provides comprehensive guidance on authentication, map creation, data upload (files, DataFrames, GeoDataFrames, URLs), lightweight annotations (pins, markers, notes), cloud database connections (Sources), SQL queries, layer styling with FSL (including vector and raster visualizations, icons, labels, popups, filters, and advanced MapLibre expressions), and finding GIS data sources.
---

# Felt Maps Skill

Felt is a collaborative web-based GIS platform for creating interactive maps from spatial data. This skill uses the `felt-python` library to programmatically create maps, upload and style geographic data, connect to cloud databases, execute SQL queries, and add annotations. You can turn datasets like GeoJSON, Shapefiles, or CSVs into styled web maps with choropleths, heatmaps, icons, labels, and custom visualizations using FSL (Felt Style Language).

# SETUP

## Installation

Always install the felt-python library before working with Felt:

```bash
pip install felt-python
```

## Using Helper Functions

This skill provides helper functions in `scripts/skill.py` for common operations. ALWAYS import them in your Python scripts:

```python
import sys
sys.path.insert(0, '<skill_base_directory>/scripts')
import skill
```

**Important:** Replace `<skill_base_directory>` with the actual skill base directory path provided in the skill context when the skill is invoked.

## Authentication

Get your Felt API token from the "Developers" tab of your Workspace settings page.

**Recommended workflow:**
1. **Check if a `.env` file exists** - If yes, skip to step 4
2. **Ask user for API token in conversation** (never use `input()`)
3. **Write it to .env file** using bash (one-time setup)
4. **Load token in Python scripts** using helper function

**Step 1: Check for existing .env file**
```bash
# Check if .env already exists
test -f .env && echo ".env file exists" || echo ".env file not found"
```

**Steps 2-3: One-time setup (only if .env doesn't exist)**
```bash
# Step 2: Ask user in conversation for their API token
# User provides: felt_pat_abc123...

# Step 3: Write to .env file using bash
echo 'FELT_API_TOKEN=felt_pat_abc123...' > .env
```

**Step 4: Load token in Python (every script)**
```python
# In Python scripts, load from .env using helper
skill.load_api_key_from_env()
# Token environment variable is now available to all felt_python functions
```

# REFERENCE

## Function Signatures

**IMPORTANT: Always use exact parameter names from these signatures.** Using incorrect parameter names will cause errors.

**Complete function signatures** (generated from felt-python v0.1.2):

```
add_source_layer(map_id: str, source_layer_params: dict[str, str], api_token: str = None)
create_custom_export(map_id: str, layer_id: str, output_format: str, filters: list = None, email_on_completion: bool = True, api_token: str | None = None)
create_embed_token(map_id: str, user_email: str = None, api_token: str = None)
create_map(title: str = None, description: str = None, public_access: str = None, basemap: str = None, lat: float = None, lon: float = None, zoom: float = None, layer_urls: list[str] = None, workspace_id: str = None, api_token: str = None)
create_project(name: str, visibility: str, api_token: str | None = None)
create_source(name: str, connection: dict[str, str], permissions: dict[str, str] = None, api_token: str | None = None)
delete_comment(map_id: str, comment_id: str, api_token: str | None = None)
delete_element(map_id: str, element_id: str, api_token: str | None = None)
delete_layer(map_id: str, layer_id: str, api_token: str | None = None)
delete_layer_group(map_id: str, layer_group_id: str, api_token: str | None = None)
delete_map(map_id: str, api_token: str | None = None)
delete_project(project_id: str, api_token: str | None = None)
delete_source(source_id: str, api_token: str | None = None)
download_layer(map_id: str, layer_id: str, file_name: str | None = None, api_token: str | None = None) -> str
duplicate_layers(duplicate_params: list[dict[str, str]], api_token: str | None = None)
duplicate_map(map_id: str, title: str = None, project_id: str = None, folder_id: str = None, api_token: str = None)
export_comments(map_id: str, format: str = 'json', api_token: str | None = None)
get_current_user(api_token: str | None = None)
get_custom_export_status(map_id: str, layer_id: str, export_id: str, api_token: str | None = None)
get_element_group(map_id: str, element_group_id: str, api_token: str | None = None)
get_export_link(map_id: str, layer_id: str, api_token: str | None = None)
get_layer(map_id: str, layer_id: str, api_token: str | None = None)
get_layer_details(map_id: str, api_token: str | None = None)
get_layer_group(map_id: str, layer_group_id: str, api_token: str | None = None)
get_map(map_id: str, api_token: str | None = None)
get_map_details(map_id: str, api_token: str | None = None)
get_project(project_id: str, api_token: str | None = None)
get_source(source_id: str, api_token: str | None = None)
list_element_groups(map_id: str, api_token: str | None = None)
list_elements(map_id: str, api_token: str | None = None)
list_elements_in_group(map_id: str, element_group_id: str, api_token: str | None = None)
list_layer_groups(map_id: str, api_token: str | None = None)
list_layers(map_id: str, api_token: str | None = None)
list_library_layers(source: str = 'workspace', api_token: str | None = None)
list_projects(workspace_id: str | None = None, api_token: str | None = None)
list_sources(workspace_id: str | None = None, api_token: str | None = None)
move_map(map_id: str, project_id: str = None, folder_id: str = None, api_token: str = None)
post_element_group(map_id: str, json_element: dict | str, api_token: str | None = None)
post_elements(map_id: str, geojson_feature_collection: dict | str, api_token: str | None = None)
publish_layer(map_id: str, layer_id: str, name: str = None, api_token: str | None = None)
publish_layer_group(map_id: str, layer_group_id: str, name: str = None, api_token: str | None = None)
refresh_file_layer(map_id: str, layer_id: str, file_name: str, api_token: str | None = None)
refresh_url_layer(map_id: str, layer_id: str, api_token: str | None = None)
resolve_comment(map_id: str, comment_id: str, api_token: str | None = None)
sync_source(source_id: str, api_token: str | None = None)
update_layer_group(map_id: str, layer_group_id: str, name: str = None, caption: str = None, ordering_key: int = None, visibility_interaction: str = None, api_token: str | None = None)
update_layer_groups(map_id: str, layer_group_params_list: list[dict[str, str | int]], api_token: str | None = None)
update_layer_style(map_id: str, layer_id: str, style: dict, api_token: str | None = None)
update_layers(map_id: str, layer_params_list: list[dict[str, object]], api_token: str | None = None)
update_map(map_id: str, title: str = None, description: str = None, public_access: str = None, api_token: str = None)
update_project(project_id: str, name: str | None = None, visibility: str | None = None, api_token: str | None = None)
update_source(source_id: str, name: str | None = None, connection: dict[str, str] | None = None, permissions: dict[str, str] | None = None, api_token: str | None = None)
upload_dataframe(map_id: str, dataframe: 'pd.DataFrame', layer_name: str, metadata: dict[str, str] = None, hints: list[dict[str, str]] = None, api_token: str | None = None)
upload_file(map_id: str, file_name: str, layer_name: str, metadata: dict[str, str] = None, hints: list[dict[str, str]] = None, lat: float = None, lng: float = None, zoom: float = None, api_token: str | None = None)
upload_geodataframe(map_id: str, geodataframe: 'gpd.GeoDataFrame', layer_name: str, metadata: dict[str, str] = None, hints: list[dict[str, str]] = None, api_token: str | None = None)
upload_url(map_id: str, layer_url: str, layer_name: str, metadata: dict[str, str] = None, hints: list[dict[str, str]] = None, api_token: str | None = None)
upsert_element_groups(map_id: str, element_groups: list[dict[str, str]], api_token: str | None = None)
upsert_elements(map_id: str, geojson_feature_collection: dict | str, api_token: str | None = None)
```

**For detailed docs on any function, use help():**
```python
help(felt_python.upload_url)
help(felt_python.create_map)
```

## Felt IDs and URLs

* Map URLs are in the format `https://felt.com/map/{map_slug}`
* The `map_slug` can be used interchangeably with the `map_id` in `felt_python` functions
* The `layer_slug` can be used interchangeably with the `layer_id` in `felt_python` functions
* Felt IDs can be in 2 formats: UUID or "Slugs"
* Slugs contain the map name (which is just ignored in the backend) and the encoded UUID

## Extracting IDs from Responses

**CRITICAL: How to get map_id and layer_id correctly**

```python
# Creating a map - returns dict with 'id' and 'url'
response = create_map(title="My Map")
map_id = response['id']    # Use this for subsequent calls
map_url = response['url']  # Share this URL with users

# Uploading data - returns dict with layer_id at top level
response = upload_url(
    map_id=map_id,
    layer_url="https://example.com/data.geojson",
    layer_name="My Layer"
)
layer_id = response['layer_id']              # At top level, not nested!
layer_group_id = response['layer_group_id']  # Also available
```

**Common response patterns:**
- `create_map()`: `{'id': 'map_id', 'url': 'https://felt.com/map/...'}`
- `upload_url/file/dataframe/geodataframe()`: `{'layer_id': '...', 'layer_group_id': '...'}`
- `get_layer()`: `{'id': '...', 'name': '...', 'status': '...', 'attributes': [...]}`
- `get_map()`: `{'id': '...', 'title': '...', 'url': '...'}`

## Understanding Response Structures (OpenAPI)

For detailed response schemas and all available fields, query the OpenAPI spec with bash tools:

```bash
# Download the OpenAPI specification
curl -o felt_openapi.json https://felt.com/api/v2/openapi.json

# See what fields get_layer returns
cat felt_openapi.json | jq '.components.schemas.Layer.properties | keys'

# See create_map response structure
cat felt_openapi.json | jq '.paths["/maps"].post.responses["200"].content["application/json"].schema'

# List all available operations
cat felt_openapi.json | jq '.paths | keys'

# See source connection type requirements
cat felt_openapi.json | jq '.components.schemas.SourceCreateConnectionParams.oneOf[].title'
```

**When to use OpenAPI spec:**
- Need to know all available fields in a response
- Understanding complex nested response structures
- Checking valid enum values for parameters
- Verifying request body schemas for source connections

# WORKFLOW GUIDANCE

## The Two-Stage Pattern

Working with Felt maps follows a two-stage pattern:

1. **Map Creation** - Create map, upload data, inspect what's available
2. **Map Styling** - Apply FSL styles, manage layers, add elements

**Why separate?** After creating and uploading data, you need to see what attributes exist before you can reference them in styling code. The output from map creation provides the context needed for styling.

**Map Creation:**
1. Create map with `create_map()`
2. Upload data:
   - **Preferred:** Upload from URL with `upload_url()`
   - **If transformations needed:** Download with geopandas, process locally (filter, transform, reproject to EPSG:4326), then upload with `upload_geodataframe()`
3. Wait for layer processing with `skill.wait_for_layer_processing()`
4. Inspect map with `skill.inspect_created_map()`

**Map Styling:**
5. Apply FSL styles using attribute names from inspection
6. Update layer properties, add elements, etc.
7. Can repeat styling operations without re-uploading

## Workflow Requirements

1. **ALWAYS ask user for API key in conversation FIRST** - Don't write input() code
2. **ALWAYS reference the API Reference section** - Use exact function signatures
3. **ALWAYS prefer URL uploads over local file processing**
4. **ALWAYS wait for layer processing to complete** using `skill.wait_for_layer_processing()`
5. **ALWAYS call `skill.inspect_created_map(map_id)` after layer processing is complete**
6. **NEVER read context.json in Python** - The context is already in your context window from inspect_created_map() output
7. **Creation and styling should typically be separate scripts** to keep attributes in context

# MAP CREATION

Get geographic data into Felt and inspect it for subsequent styling.

**This phase produces:**
- Map URL (to view in browser)
- Map ID and layer IDs (to use in styling code, output to console and saved to context.json)
- Layer attributes (field names and types for FSL styles, output to console)

## Creating a Map

Create a new Felt map to hold your data.

**Function:**
```python
create_map(
    title: str = None,
    description: str = None,
    public_access: str = None,
    basemap: str = None,
    lat: float = None,
    lon: float = None,
    zoom: float = None,
    layer_urls: list[str] = None,
    workspace_id: str = None,
    api_token: str = None
)
```

**Parameters:**

- **`title`** - Map title (ALWAYS set a title, defaults to "Untitled Map")
- **`description`** - Description shown in the map legend
- **`basemap`** - Basemap style. Valid values:
  - `"default"` - Felt's default basemap
  - `"light"` - Light theme
  - `"dark"` - Dark theme
  - `"satellite"` - Satellite imagery
  - Custom raster tile URL with `{x}`, `{y}`, `{z}` parameters (e.g., `"https://tile.openstreetmap.org/{z}/{x}/{y}.png"`)
  - Hex color string (e.g., `"#ff0000"` for solid red background)

- **`public_access`** - Access level. Valid values:
  - `"private"` - Only workspace members with explicit access
  - `"view_only"` - Anyone with link can view (default)
  - `"view_and_comment"` - Anyone can view and comment
  - `"view_comment_and_edit"` - Anyone can view, comment, and edit

- **`lat`, `lon`, `zoom`** - Initial map viewport (used if no data uploaded yet)

- **`layer_urls`** - Array of raster tile URLs to add as layers at creation time

- **`workspace_id`** - Workspace to create map in (defaults to latest used workspace)

## Uploading Data

**Prefer URL uploads** - Upload data directly from URLs without downloading locally.

**Functions:**
- `upload_url(map_id, layer_url, layer_name, ...)` - Upload from URL (PREFERRED)
- `upload_file(map_id, file_name, layer_name, ...)` - Upload local file
- `upload_geodataframe(map_id, geodataframe, layer_name, ...)` - Upload GeoDataFrame
- `upload_dataframe(map_id, dataframe, layer_name, ...)` - Upload DataFrame

**Returns:** `{'layer_id': 'layer-xxx', 'layer_group_id': 'group-xxx'}`

**Only download/process locally if you need:**
- Transformations or data cleaning
- Merging multiple datasets
- Spatial intersections/joins
- Aggregations or calculated fields

## Inspecting Your Map

After uploading data and waiting for processing, inspect the map to see all layers and their attributes.

**What `inspect_created_map(map_id)` does:**
- Fetches complete layer information including attributes and current styles
- Outputs comprehensive context as JSON to console (enters your context window for subsequent steps)
- Writes same context to `context.json` for later retrieval

**Context includes:**
- Map ID, name, and URL
- For each layer: ID, name, attributes (with types), and current style (FSL)

## Example

```python
from felt_python import create_map, upload_url
import skill

skill.load_api_key_from_env()

# Create map
map_response = create_map(title="My Analysis")
map_id = map_response['id']

# Upload data
upload_response = upload_url(
    map_id=map_id,
    layer_url="https://example.com/data.geojson",
    layer_name="My Layer"
)
layer_id = upload_response['layer_id']

# Wait for processing
layer = skill.wait_for_layer_processing(map_id, layer_id, timeout_s=30)

# Inspect the map
skill.inspect_created_map(map_id)
```

# MAP STYLING

With map creation complete, you can now style and manipulate your map.

**Retrieving Context:** If you need the map_id, layer_id, attributes or styles later in the conversation, read the context.json file:
```bash
cat context.json
```

**Styling is iterative:** You can run styling operations multiple times without re-creating the map:
- Try different FSL styles
- Add or modify elements (annotations)
- Update layer properties (names, ordering, visibility)
- Update map settings (basemap, access level)

## Default-Aware Styling

**IMPORTANT:** Layers automatically receive default styles when created. When writing FSL to update styles, **be aware of the existing default properties** so you can retain good defaults and only change what you need.

**Guidelines:**
- Write complete FSL, but retain properties you want to keep (like opacity, size, version)
- Most common: Tweaking colors, sizes, opacity while keeping the rest
- Less common: Changing visualization type entirely (simple → numeric → categorical) requires all new FSL

## Styling with FSL

Apply visual styles using Felt Style Language (FSL).

```python
import felt_python
import skill

skill.load_api_key_from_env()

map_id = "map-abc123"
layer_id = "layer-xyz789"

# Write FSL informed by the existing style
# Use attributes from inspection, retain good defaults where appropriate
style = {
    "version": "2.3.1",
    "type": "numeric",
    "config": {
        "numericAttribute": "population",  # From context: available attributes
        "labelAttribute": ["city_name"]     # From context: available attributes
    },
    "paint": {"color": "@galaxy", "size": [5, 20]}  # Consider existing paint properties
}

felt_python.update_layer_style(map_id, layer_id, style)
```

You can run styling scripts multiple times with different styles to iterate on your visualization.


## Felt Style Language (FSL)

FSL is Felt's JSON-based styling system for map layers. It provides a declarative way to create visualizations with automatic classification, color palettes, and optimized rendering.

**IMPORTANT: Always use version "2.3.1"** in your FSL styles.

---

### FSL Core Patterns

Understanding these patterns will help you work with all FSL features.

#### Pattern 1: Shortcut vs Explicit

FSL consistently uses this pattern: **Object with `type` = shortcut (Felt computes), Array = explicit (you control)**.

**Steps (classification breaks):**
- Shortcut: `{"type": "jenks", "count": 5}` → Felt computes optimal breaks
- Explicit: `[0, 100, 500, 1000, 5000]` → You specify exact breaks

**Categories:**
- Shortcut: `{"type": "top", "count": 10}` → Felt picks top categories
- Explicit: `["residential", "commercial", "industrial"]` → You list categories

**Colors:**
- Shortcut: `"@galaxy"` → Felt palette
- Explicit: `["#FF0000", "#00FF00", "#0000FF"]` → Your hex codes

**Mix approaches:**

| Steps | Colors | Result |
|-------|--------|--------|
| `{"type": "jenks"}` | `"@galaxy"` | Fully automatic |
| `{"type": "jenks"}` | `["#FF0000", "#00FF00"]` | Auto breaks, custom colors |
| `[0, 100, 500]` | `"@galaxy"` | Custom breaks, auto colors |
| `[0, 100, 500]` | `["#FF0000", "#00FF00"]` | Fully manual |

**When to use shortcuts vs explicit:**

- **Use shortcuts (DEFAULT)** - `@galaxy`, `{"type": "jenks"}`, `{"type": "top", "count": 10}`
  - For most visualizations where Felt's automatic choices work well
  - When you don't need specific colors, breaks, or categories
  - Faster to implement and adaptable to different datasets

- **Use explicit values** - `["#FF0000", "#00FF00"]`, `[0, 100, 500]`, `["park", "water"]`
  - Standard color schemes (USDM drought levels, USGS land cover/elevation, FEMA flood zones, seismic magnitude colors)
  - Brand or organization-specific colors must be followed exactly
  - User specifies particular colors, breaks, or categories
  - Precise control needed for technical/scientific visualization

---

### FSL Structure

Every FSL style has this structure:

```json
{
  "version": "2.3.1",
  "type": "simple",      // Visualization type
  "config": {},          // Visualization configuration
  "paint": {},           // Visual styling
  "label": {},           // Optional: Label styling
  "legend": {},          // Optional: Legend customization
  "popup": {},           // Optional: Popup configuration
  "attributes": {},      // Optional: Attribute display names
  "filters": {}          // Optional: Data filter
}
```

---

### Default Styles

When you upload a layer to Felt, it **automatically receives default styling** based on its geometry type. When writing FSL, you're typically **overriding some properties while keeping others**.

#### Default Appearance by Geometry

**IMPORTANT: Always include these default properties in your FSL, even when using default values.**

Felt assigns colors from a 20-color default palette based on layer order (1st layer→color #1, 2nd→color #2, cycling through). Palette includes teals, greens, blues, purples, reds, oranges, and grays. When writing FSL, always include the `color` property (SimplePalette color, Felt palette shortcut, or custom hex).

**Labels are hidden by default.** To enable labels, see [Label Configuration](#label-configuration).

#### Paint Properties by Geometry Type

| Property | Point | Line | Polygon | Notes |
|----------|-------|------|---------|-------|
| **color** | Fill color | Line color | Fill color | **Required everywhere** |
| **size** | Radius (px) | Width (px) | ❌ N/A | **Different meanings!** Points: radius, Lines: width. **Polygons have NO size property** |
| **opacity** | ✅ 0.9 | ✅ 1.0 | ✅ 0.8 | 0-1 transparency (defaults shown) |
| **strokeColor** | Border | ❌ N/A | Border | Defaults to [`"auto"`](#smart-color-auto) (contrasting border) |
| **strokeWidth** | Border width | ❌ N/A | Border width | Pixels (default: 1) |
| **dashArray** | ❌ N/A | ✅ | ❌ N/A | `[dash, gap]` pattern in pixels |
| **lineCap** | ❌ N/A | ✅ `"round"` | ❌ N/A | Line endings: "butt" \| "round" \| "square" |
| **lineJoin** | ❌ N/A | ✅ `"round"` | ❌ N/A | Line corners: "bevel" \| "round" \| "miter" |
| **isSandwiched** | ❌ N/A | ❌ N/A | ✅ false | true = below basemap labels, false = above |
| **iconImage** | ✅ | ❌ N/A | ❌ N/A | Icon/emoji name (see [Icon Reference](#icon-reference)) |
| **paint array** | ✅ | ✅ | ✅ | Multiple layers (e.g., casing effects) |

**Example paint objects:**
```json
// Point (circle or icon)
{"color": "hsl(161,30%,45%)", "size": 4, "opacity": 0.9, "strokeColor": "auto", "strokeWidth": 1}

// Line
{"color": "hsl(61,40%,45%)", "size": 2, "opacity": 1.0, "lineCap": "round", "lineJoin": "round"}

// Polygon
{"color": "hsl(104,33%,57%)", "opacity": 0.8, "strokeColor": "auto", "strokeWidth": 1, "isSandwiched": false}
```

**Common mistakes:**
```json
// ❌ WRONG - polygons don't have size!
{"type": "simple", "paint": {"size": 5}}

// ✅ CORRECT - use strokeWidth for borders
{"type": "simple", "paint": {"strokeWidth": 2, "strokeColor": "#000"}}
```

---

### Geometry Types & Visualization Types

#### Which Viz Types Work With Which Geometries

| Viz Type | Point | Line | Polygon | Raster |
|----------|-------|------|---------|--------|
| `simple` | ✅ | ✅ | ✅ | ✅ |
| `categorical` | ✅ | ✅ | ✅ | ✅ |
| `numeric` | ✅ | ✅ | ✅ | ✅ |
| `heatmap` | ✅ | ❌ | ❌ | ❌ |
| `h3` | ✅ | ❌ | ❌ | ❌ |
| `hillshade` | ❌ | ❌ | ❌ | ✅ |

---

### Paint Arrays (Layered Styling)

The `paint` property can be an **array of paint objects** to create layered effects:

```json
{
  "paint": [
    {
      "color": "#3B82F6",
      "size": 10
    },
    {
      "color": "#FFFFFF",
      "size": 12
    }
  ]
}
```
→ Each object in the array is rendered as a separate layer

**Common uses:**
- **Casing/outlines:** Larger background layer + smaller foreground layer
- **Layered effects:** Multiple visual treatments on the same features
- **Complex styling:** Different properties per layer

**Rendering order:** Layers render from last to first in the array (last = bottom, first = top)

---

### Smart Color: "auto"

`"auto"` computes contrasting colors automatically. Always include `"auto"` explicitly for strokeColor (points/polygons) and label colors.

**Works for:** `strokeColor` (points/polygons), label `color`, label `haloColor`

**Example:**
```json
{
  "paint": {
    "color": "#3B82F6",
    "strokeColor": "auto"  // Computes contrasting border
  },
  "label": {
    "color": "auto",       // Theme-aware text color
    "haloColor": "auto"    // Contrasting outline
  }
}
```

---

### Zoom-Based Styling

Properties respond to map zoom level, creating responsive visualizations.

**Properties that support zoom ramping:**
- **Paint:** `size`, `color`, `strokeColor`, `strokeWidth`, `opacity`, `intensity`, `weight`, `iconFill`, `iconStroke`, `iconSize`
- **Labels:** `fontSize`, `haloWidth`, `color`, `haloColor`, `offset`, `maxLineChars`

**Explicit format (use this by default):**
```json
{
  "paint": {
    "size": {
      "linear": [
        [8, 5],      // At zoom 8: 5px
        [12, 10],    // At zoom 12: 10px
        [18, 18]     // At zoom 18: 18px
      ]
    }
  }
}
```

**Label visibility:** Use `minZoom`/`maxZoom` to control when labels appear, not `fontSize`:
```json
{
  "label": {
    "minZoom": 10,       // Hide labels below zoom 10
    "fontSize": [12, 16] // Size grows within visible range
  }
}
```

---

### Color Interpolation

When specifying colors in FSL, behavior differs based on visualization type and whether you use a palette shortcut or an explicit color array.

#### Palette Shortcuts (Recommended)

Palette shortcuts like `"@galaxy"` automatically provide the right number of colors for any visualization—classed or continuous:
```json
{
  "config": {
    "numericAttribute": "population",
    "steps": {"type": "quantiles", "count": 5}
  },
  "paint": {
    "color": "@galaxy"
  }
}
```

#### Explicit Color Arrays

**For classed maps:** You MUST provide exactly one color per class. No interpolation.
```json
// ✅ CORRECT - 4 classes, 4 colors
{
  "config": {"steps": [0, 100, 500, 1000, 5000]},
  "paint": {"color": ["#FFEDA0", "#FED976", "#FD8D3C", "#FC4E2A"]}
}

// ❌ WRONG - 4 classes, 2 colors
{
  "config": {"steps": [0, 100, 500, 1000, 5000]},
  "paint": {"color": ["#FFEDA0", "#FC4E2A"]}
}
```

**For continuous maps:** Explicit arrays DO interpolate smoothly:
```json
{
  "config": {"steps": {"type": "continuous"}},
  "paint": {"color": ["#0000FF", "#FF0000"]}
}
```

#### Counting Classes

- Shortcut: `{"type": "quantiles", "count": 5}` → 5 classes
- Explicit: `[0, 100, 500, 1000, 5000]` → 4 classes (N breaks = N-1 classes)

#### Quick Reference

| Viz Type | Color Format | Behavior |
|----------|--------------|----------|
| Classed | Palette shortcut | ✅ Automatic |
| Classed | Explicit array | ⚠️ One color per class required |
| Continuous | Either | ✅ Interpolates |

---

### Visualization Types

#### 1. Simple Visualization

Uniform styling for all features.

```json
{
  "version": "2.3.1",
  "type": "simple",
  "paint": {
    "color": "hsl(161,30%,45%)",  // From SimplePalette
    "size": 4,                     // Default for points
    "opacity": 0.9,
    "strokeColor": "auto",         // Default border color
    "strokeWidth": 1               // Default border width
  }
}
```

**Use for:** Basic maps, background layers, uniform datasets

**Note:** This example shows point defaults. See [Paint Properties by Geometry Type](#paint-properties-by-geometry-type) for line and polygon defaults.

---

#### 2. Categorical Visualization

Style features by category values (land use, type, status, etc.).

**Categorical vs Numeric:**
- **Categorical** - Works with strings or numbers. Use for discrete known values.
- **Numeric** - Works with numbers only. Use for classification methods (jenks, quantiles) or continuous gradients.

**Choosing a palette for categorical visualizations:**
- **Categorical palette** (`@catPalette1`) - For nominal data with no inherent order (land use types, species, facility types). Distinct colors, no hierarchy implied.
- **Sequential palette** (`@ylRed`, `@galaxy`) - For ordinal data with ranked levels (drought severity D0-D4, risk levels 1-5, Low/Medium/High). Color progression communicates order.

**When to use each format:**
- **Format 1 (shortcuts)** - DEFAULT - See "When to use shortcuts vs explicit" in FSL Core Patterns above
- **Format 2 (explicit categories)** - When you need specific categories (see FSL Core Patterns for when to use explicit values)

**Format 1: Automatic category selection (shortcut)**

**DEFAULT: Use `{"type": "top", "count": 10}` unless the user specifically requests "all" or a different count.**

```json
{
  "version": "2.3.1",
  "type": "categorical",
  "config": {
    "categoricalAttribute": "land_use",
    "categories": {"type": "top", "count": 10},  // DEFAULT
    "showOther": true                             // REQUIRED
  },
  "paint": {
    "color": "@catPalette4",      // Palette shortcut
    "size": 4,                     // Point default (see geometry-specific defaults)
    "opacity": 0.9,                // Point default (see geometry-specific defaults)
    "strokeColor": "auto",         // Default border color
    "strokeWidth": 1               // Default border width
  },
  "legend": {
    "displayName": {
      "park": "Parks & Recreation",
      "water": "Water Bodies"
    }
  }
}
```

**Category shortcuts:**
- `{"type": "top", "count": 10}` - Shows the 10 most frequent categories
- `{"type": "top", "count": 5}` - Shows the 5 most frequent categories (when user specifies a different count)
- `{"type": "all"}` - Shows all unique categories (only when user says "all categories" or "show every type")

**How "top" works:** Takes the N most frequent values from the data. For example, if your data has 50 land use types, `{"type": "top", "count": 10}` shows only the 10 that appear most often.

**ALWAYS include `showOther: true`** in config to show remaining values as "Other".

**Format 2: Explicit category list**

Use this when the user's request explicitly names specific categories, or when standard color schemes apply (USDM drought, USGS land cover, FEMA flood zones, brand colors).

**Rules for Format 2:**
1. Explicit category array → `["park", "water", "building"]` or `[0, 1, 2, 3, 4]`
2. Color → palette shortcut `@catPalette4` **OR** explicit color array for standard color schemes
3. **ALWAYS include `legend.displayName`** with human-readable names for each category
4. **ALWAYS include `showOther: true`**

```json
{
  "version": "2.3.1",
  "type": "categorical",
  "config": {
    "categoricalAttribute": "land_use",
    "categories": ["park", "water", "building", "road"],
    "showOther": true
  },
  "paint": {
    "color": ["#FFFF00", "#FCD37F", "#FFAA00", "#E60000"],
    "size": 4,
    "opacity": 0.9,
    "strokeColor": "auto",
    "strokeWidth": 1
  },
  "legend": {
    "displayName": {
      "park": "Parks & Recreation",
      "water": "Water Bodies",
      "building": "Buildings",
      "road": "Roads"
    }
  }
}
```
---

#### Varying Multiple Properties by Category/Class

In categorical and numeric classed visualizations, **any paint property can be an array** to vary it by category or class. This applies the Object vs Array pattern to all properties, not just color.

**⚠️ IMPORTANT - Default behavior: Use single values**

For most categorical maps, use **single values** for size/opacity/strokeWidth:
- `"size": 4` - all categories same size (DEFAULT for points)
- `"opacity": 0.9` - all categories same opacity (DEFAULT for points)
- `"strokeWidth": 1` - all categories same stroke (DEFAULT)

**Only use arrays when the user explicitly wants different sizes/opacities per category.** This is uncommon.

**Example: Varying size, color, and opacity by category (ADVANCED - RARELY USED)**

```json
{
  "type": "categorical",
  "config": {
    "categoricalAttribute": "building_type",
    "categories": ["residential", "commercial", "industrial"]
  },
  "paint": {
    "color": ["#90EE90", "#4682B4", "#A9A9A9"],     // Different color per category
    "size": [4, 8, 12],                             // Different size per category
    "opacity": [0.6, 0.8, 1.0],                     // Different opacity per category
    "strokeWidth": [1, 2, 3]                        // Different stroke width per category
  }
}
```
→ Residential: light green, 4px, 60% opacity, 1px stroke
→ Commercial: blue, 8px, 80% opacity, 2px stroke
→ Industrial: gray, 12px, 100% opacity, 3px stroke

**Example: Varying multiple properties in numeric classed viz**

```json
{
  "type": "numeric",
  "config": {
    "numericAttribute": "magnitude",
    "steps": [0, 3, 5, 7]  // 4 steps = 3 classes
  },
  "paint": {
    "color": ["#FFFF00", "#FF6347", "#8B0000"],     // Yellow → Red-Orange → Dark Red
    "size": [3, 6, 10],                             // Small → Medium → Large
    "opacity": [0.7, 0.85, 1.0]                     // More transparent → Fully opaque
  }
}
```
→ Class 1 (0-3): Yellow, 3px, 70% opacity
→ Class 2 (3-5): Red-Orange, 6px, 85% opacity
→ Class 3 (5-7): Dark Red, 10px, 100% opacity

**Which properties can be arrays:**

| Property | Works in Categorical | Works in Numeric Classed | Notes |
|----------|---------------------|--------------------------|-------|
| `color` | ✅ | ✅ | Most common |
| `size` | ✅ | ✅ | Radius (points) or width (lines) |
| `opacity` | ✅ | ✅ | 0-1 per category/class |
| `strokeColor` | ✅ | ✅ | Border color per category/class |
| `strokeWidth` | ✅ | ✅ | Border width per category/class |
| `dashArray` | ✅ (lines) | ✅ (lines) | Array of arrays: `[[5,5], [10,5], [2,4]]` |
| `iconImage` | ✅ (points) | ✅ (points) | Different icon per category: `["star", "circle", "square"]` |

**Pattern:**
- **Single value** → Same for all categories/classes
- **Array of values** → One value per category/class
- **Array lengths must match** the number of categories or classes

**Common use case: Size by category, color by palette**

```json
{
  "type": "categorical",
  "config": {
    "categoricalAttribute": "priority",
    "categories": ["low", "medium", "high", "critical"]
  },
  "paint": {
    "color": "@ylRed",        // Palette shortcut (4 colors)
    "size": [4, 6, 8, 12]     // Different size per priority level
  }
}
```

**This pattern extends FSL Core Pattern 1:**
- **Single value** = Apply same to all (shortcut)
- **Array of values** = Specify per category/class (explicit control)

---

#### 3. Numeric Visualization

Style by numeric values with classification methods.

**Classification Methods:**

| Method | What It Does | Best For | Format |
|--------|-------------|----------|--------|
| `jenks` | Natural breaks | Most cases (default) | `{"type": "jenks", "count": 5}` |
| `quantiles` | Equal features per class | Balanced representation | `{"type": "quantiles", "count": 5}` |
| `equal-intervals` | Equal-sized bins | When ranges matter | `{"type": "equal-intervals", "count": 6}` |
| `stddev` | Standard deviation | Show variation from mean | `{"type": "stddev", "count": 5}` |
| `geo-intervals` | Geographic intervals | Spatial distribution | `{"type": "geo-intervals", "count": 5}` |
| `continuous` | Smooth gradient | No discrete classes | `{"type": "continuous"}` |

**Automatic classification (shortcut):**

```json
{
  "version": "2.3.1",
  "type": "numeric",
  "config": {
    "numericAttribute": "population",
    "steps": {"type": "jenks", "count": 5}  // Felt computes breaks
  },
  "paint": {
    "color": "@galaxy",           // Palette shortcut
    "size": [5, 48]               // Optional: Min/max size for proportional scaling
  }
}
```

**Manual classification (explicit):**

```json
{
  "version": "2.3.1",
  "type": "numeric",
  "config": {
    "numericAttribute": "magnitude",
    "steps": [0, 4, 5, 6, 7]      // Your exact break points (5 breaks = 4 classes)
  },
  "paint": {
    "color": ["#FFFF00", "#FFA500", "#FF0000", "#8B0000"]  // 4 colors for 4 classes
  }
}
```

**Continuous/unclassed:**

```json
{
  "version": "2.3.1",
  "type": "numeric",
  "config": {
    "numericAttribute": "temperature",
    "steps": {"type": "continuous"}
  },
  "paint": {
    "color": ["#0000FF", "#FF0000"]  // Smooth gradient from blue to red
  }
}
```

**Proportional symbols (size only, no color classes):**

```json
{
  "version": "2.3.1",
  "type": "numeric",
  "config": {
    "numericAttribute": "population",
    "steps": {"type": "continuous"}
  },
  "paint": {
    "color": "hsl(161,30%,45%)",  // From SimplePalette
    "size": [3, 30],               // Default min/max size - scales proportionally with values
    "opacity": 0.9,
    "strokeColor": "auto",
    "strokeWidth": 1
  }
}
```

**Key points:**
- N break points = N-1 classes (5 breaks = 4 classes)
- Colors/sizes array length = number of classes
- Continuous interpolates colors smoothly (uses HCL color space)
- For raster data: Use `"band": 1` instead of `numericAttribute`

---

#### 4. Heatmap Visualization

Density visualization for point features only.

```json
{
  "version": "2.3.1",
  "type": "heatmap",
  "config": {},
  "paint": {
    "color": "@redOrHeat",   // Yellow → orange → red → dark red gradient
    "size": 10,              // Point influence radius (default: 10)
    "intensity": 0.5,        // Heatmap strength (default: 0.5)
    "opacity": 0.9           // Heatmap opacity (default: 0.9)
  }
}
```

**Key properties:**
- `color`: Array from low to high density (use heatmap palettes: `@redOrHeat`, `@purpYlPink`, `@lightningHeat`)
- `size`: Controls point size/radius of influence (default: 10)
- `intensity`: Controls overall heatmap intensity (default: 0.5)
- `opacity`: Controls heatmap transparency (default: 0.9)

**Note:** Heatmaps do not support labels.

---

#### 5. H3 Hexagon Binning

Aggregate point data into H3 hexagonal cells.

```json
{
  "version": "2.3.1",
  "type": "h3",
  "config": {
    "numericAttribute": "population",     // Optional: Attribute to aggregate
    "aggregation": "count",               // count (default), sum, mean, min, max
    "baseBinLevel": 3,                    // H3 resolution (0-15, default: 3)
    "binMode": "fixed",                   // "fixed" (default) or "auto"
    "steps": {"type": "quantiles", "count": 5}  // Classification method (default)
  },
  "paint": {
    "color": "@copper",                   // Sequential palette (default)
    "opacity": 0.9,                       // Default
    "strokeColor": "auto",                // Default
    "strokeWidth": 1                      // Default
  }
}
```

**Config properties:**
- `numericAttribute`: What to aggregate (optional - omit for count only)
- `aggregation`: `"count"` (default) | `"sum"` | `"mean"` | `"min"` | `"max"`
- `baseBinLevel`: H3 resolution 0-15 where 0 is coarsest, 15 is finest (default: 3)
- `binMode`: `"fixed"` (default) | `"auto"`
- `steps`: Same classification as numeric viz (default: quantiles with 5 classes)

**Paint properties:**
- `color`: Use any sequential palette (`@copper`, `@riverine`, `@galaxy`, `@neptune`, `@ylRed`, etc.)
- `opacity`: 0.9 (default)
- `strokeColor`: "auto" (default)
- `strokeWidth`: 1 (default)

---

#### 6. Raster Visualizations

For GeoTIFF and other raster formats.

**Numeric Raster (continuous or classed):**

```json
{
  "version": "2.3.1",
  "type": "numeric",
  "config": {
    "band": 1,                            // Raster band number
    "steps": {"type": "continuous"},      // or {"type": "quantiles", "count": 6} or [0, 5, 10]
    "rasterResampling": "linear",         // "linear" (smooth) or "nearest" (pixelated)
    "noData": -9999,                      // Optional: Value to treat as transparent
    "method": {"NDVI": {"NIR": 1, "R": 2}}  // Optional: Raster algebra
  },
  "paint": {
    "color": "@mpaInferno",
    "opacity": 1.0
  }
}
```

**Raster config properties:**
- `band`: Which raster band to use (1-indexed)
- `steps`: Classification method (same as numeric)
- `rasterResampling`: `"linear"` (smooth) or `"nearest"` (pixelated)
- `noData`: Value to treat as no-data/transparent
- `method`: Raster algebra operations
  - `{"NDVI": {"NIR": 1, "R": 2}}` - Normalized Difference Vegetation Index
  - `{"NDWI": {"G": 1, "NIR": 2}}` - Normalized Difference Water Index
  - `{"NDMI": {"NIR": 1, "SWIR": 2}}` - Normalized Difference Moisture Index

**Categorical Raster:**

```json
{
  "version": "2.3.1",
  "type": "categorical",
  "config": {
    "band": 1,
    "categories": {"type": "all"},    // For raster: "all" is common (fixed value set). For vector: default to top 10
    "showOther": true,                 // Show "Other" category
    "rasterResampling": "nearest"     // Usually "nearest" for categorical
  },
  "paint": {
    "color": "@catPalette1"
  }
}
```

**Hillshade:**

```json
{
  "version": "2.3.1",
  "type": "hillshade",
  "config": {
    "band": 1,
    "rasterResampling": "linear"
  },
  "paint": {
    "opacity": 1.0,
    "source": 315,      // Optional: Light angle in degrees (0=N, 90=E, 180=S, 270=W)
    "intensity": 0.76   // Optional: Effect strength
  }
}
```

**Simple Raster (no color mapping):**

```json
{
  "version": "2.3.1",
  "type": "simple",
  "paint": {
    "opacity": 1.0
  }
}
```

---

### Color Palettes

Felt provides built-in color palettes that you can reference with `"@paletteName"`. These are convenient shortcuts, but you can always use your own hex colors or any color scheme instead.

**Sequential Palettes (low → high):**

| Palette | Description |
|---------|-------------|
| `@galaxy` | Purple to yellow (popular default) |
| `@ylRed` | Yellow to red |
| `@ylGrn` | Yellow to green |
| `@purpYl` | Purple to yellow |
| `@pinkYl` | Pink to yellow |
| `@lightning` | Lightning gradient |
| `@copper` | Copper gradient |
| `@spruce` | Spruce green |
| `@riverine` | Water gradient |
| `@neptune` | Blue gradient |
| `@violet` | Violet gradient |
| `@purple` | Purple gradient |

**Diverging Palettes (two directions from center):**

| Palette | Description |
|---------|-------------|
| `@bluRd` | Blue to red |
| `@tealOr` | Teal to orange (colorblind-safe) |
| `@bluBr` | Blue to brown |
| `@grnOr` | Green to orange |
| `@purGrn` | Purple to green |
| `@weath` | Weather gradient |

**Categorical Palettes (distinct colors):**

| Palette | Description |
|---------|-------------|
| `@catPalette1` | Categorical color scheme 1 |
| `@catPalette2` | Categorical color scheme 2 |
| `@catPalette3` | Categorical color scheme 3 |
| `@catPalette4` | Categorical color scheme 4 |
| `@catPalette5` | Categorical color scheme 5 |
| `@catPalette6` | Categorical color scheme 6 |
| `@catPalette7` | Categorical color scheme 7 |
| `@catPalettePT1` | Paul Tol categorical palette 1 |
| `@catPalettePT2` | Paul Tol categorical palette 2 |

**Heatmap Palettes (for point density layers):**

| Palette | Description |
|---------|-------------|
| `@redOrHeat` | Yellow → orange → red → dark red |
| `@purpYlHeat` | Light yellow → orange → red → purple |
| `@lightningHeat` | Blue → teal → green → yellow |
| `@ylGrnHeat` | Dark green → light green → yellow |
| `@bluRdHeat` | Blue → white → red |
| `@tealRedHeat` | Teal → yellow → orange → red |
| `@geyser` | Green → yellow → orange → red |
| `@purpYlPink` | Purple → teal → yellow → orange → pink |

**Raster Palettes (for raster/elevation layers):**

| Palette | Description |
|---------|-------------|
| `@feltGrays` | Grayscale gradient (9 steps) |
| `@cbBlues` | ColorBrewer blues (9 steps) |
| `@cbPurples` | ColorBrewer purples (9 steps) |
| `@feltPinks` | Pink gradient (9 steps) |
| `@cmOceanGreens` | Ocean greens gradient (9 steps) |
| `@pattFeltOcean` | Teal ocean gradient (9 steps) |
| `@cmOceanDeep` | Deep ocean gradient (9 steps) |
| `@mpaInferno` | Matplotlib inferno (9 steps) |
| `@mplPlasma` | Matplotlib plasma (9 steps) |
| `@mplVirdis` | Matplotlib viridis - perceptually uniform (9 steps) |
| `@cividis` | Cividis - colorblind-safe (9 steps) |
| `@feltYlRed` | Felt yellow to red (9 steps) |
| `@feltWeath` | Felt weather gradient (9 steps) |
| `@feltHeat` | Felt heat gradient (9 steps) |
| `@feltVibrant` | Felt vibrant gradient (9 steps) |
| `@nclBlOrRed` | NCL blue-orange-red diverging (9 steps) |
| `@cbRedYlGrn` | ColorBrewer red-yellow-green diverging (9 steps) |
| `@cbBrBG` | ColorBrewer brown-blue-green diverging (9 steps) |
| `@veg` | Vegetation gradient (9 steps) |
| `@nasaNDVI` | NASA NDVI vegetation index (9 steps) |
| `@terrain` | Terrain elevation gradient (9 steps) |
| `@rTerrain` | R terrain gradient (9 steps) |
| `@feltHypso` | Felt hypsometric tints (9 steps) |
| `@wikiTerrain` | Wikipedia terrain gradient (9 steps) |

**Note:** Raster palettes support numbered variants (e.g., `@feltGrays2`, `@feltGrays3`, ..., `@feltGrays9`) to specify different step counts.

**Choosing the right palette type:**

Different visualization types need different palette types:

| Visualization Type | Geometry | Use This Palette Type | Examples |
|-------------------|----------|----------------------|----------|
| Numeric (sequential data) | Point, Line, Polygon | **Sequential** | `@galaxy`, `@ylRed`, `@purple`, `@neptune` |
| Numeric (diverging data) | Point, Line, Polygon | **Diverging** | `@bluRd`, `@tealOr`, `@grnOr`, `@weath` |
| Categorical | Point, Line, Polygon | **Categorical** | `@catPalette1`-`@catPalette7`, `@catPalettePT1` |
| Heatmap (density) | Point only | **Heatmap** | `@redOrHeat`, `@purpYlPink`, `@lightningHeat` |
| Raster (elevation/terrain) | Raster | **Raster** | `@terrain`, `@feltHypso`, `@wikiTerrain` |
| Raster (scientific data) | Raster | **Raster** | `@mplVirdis`, `@mpaInferno`, `@cividis` |

**When to use sequential vs diverging:**
- **Sequential** (`@galaxy`, `@ylRed`): Data with one direction (population density, elevation, temperature)
- **Diverging** (`@bluRd`, `@tealOr`): Data with meaningful center point (temperature anomaly, change from baseline, +/− values)

---

### Label Configuration

Add text labels to features. Labels require two parts:

1. **`config.labelAttribute`** - Which field(s) to display
2. **`label` block** - How to style the labels

**Basic example:**

```json
{
  "config": {
    "labelAttribute": ["name"]  // Field to display
  },
  "label": {
    "color": "auto",       // Default: theme-aware text color
    "fontSize": 13,        // Default: 13px
    "haloColor": "auto",   // Default: contrasting outline
    "haloWidth": 1         // Default: 1px outline
  }
}
```

**Note:** Label `color` and `haloColor` default to `"auto"` for theme-aware, contrasting colors. See [Smart Color: "auto"](#smart-color-auto) section for details.

**Complete label properties:**

```json
{
  "label": {
    "color": "auto",              // Text color (default: "auto")
    "fontSize": 13,               // Size in pixels (default: 13)
    "fontStyle": "normal",        // "normal" | "italic" (default: "normal")
    "fontWeight": 500,            // Font weight (default: 500)
    "haloColor": "auto",          // Outline color (default: "auto")
    "haloWidth": 1,               // Outline width (default: 1)
    "justify": "auto",            // Text alignment (default: "auto")
    "letterSpacing": 0,           // Letter spacing (default: 0)
    "lineHeight": 1.2,            // Line height multiplier (default: 1.2)
    "maxLineChars": 10,           // Max chars per line (default: 10)
    "maxZoom": 23,                // Max zoom to show labels (default: 23)
    "minZoom": 1,                 // Min zoom to show labels (default: 1)
    "offset": [8, 8],             // [x, y] offset in pixels (default: [8, 8])
    "padding": 2,                 // Padding around label (default: 2)
    "placement": "auto",          // Label placement (default: "auto")
    "textTransform": "none",      // "none" | "uppercase" | "lowercase" (default: "none")
    "repeatDistance": 250         // Optional: Distance between repeated line labels
  }
}
```

**Placement options:**
- **For points:** `"auto"`, `"N"`, `"NE"`, `"E"`, `"SE"`, `"S"`, `"SW"`, `"W"`, `"NW"`, `"Center"`
- **For lines:** `"Above"`, `"Center"`, `"Below"`

**Example with zoom control:**

```json
{
  "config": {
    "labelAttribute": ["city_name"]
  },
  "label": {
    "color": "#000000",
    "fontSize": 16,
    "haloColor": "#FFFFFF",
    "haloWidth": 2,
    "minZoom": 5,      // Only show when zoomed in past level 5
    "fontStyle": "italic"
  }
}
```

---

### Legend Block

Controls legend display. Optional - can omit or use `{}` if no customization needed.

The legend block controls how legends display in the map. This block is optional - you can omit it entirely or use an empty object {} if no custom labels are needed.
The key field is displayName, which maps category/numeric values to human-readable labels.

**For categorical visualizations (custom labels):**

```json
{
  "legend": {
    "displayName": {
      "park": "Parks & Recreation",
      "water": "Water Bodies",
      "building": "Buildings"
    }
  }
}
```

**For numeric visualizations (custom range labels):**

```json
{
  "legend": {
    "displayName": {
      "0": "< 1,000",
      "1": "1,000 - 5,000",
      "2": "5,000 - 10,000",
      "3": "> 10,000"
    }
  }
}
```

**Or just provide a title:**

```json
{
  "legend": {
    "displayName": "Population Density"
  }
}
```

**Note:** To control whether a layer appears in the legend at all, use `update_layers()` with `legend_visibility: "show"` or `"hide"` (not part of FSL).

---

### Legend Visibility Control

**IMPORTANT:** Layer legend visibility is controlled by **layer-level properties**, not FSL style properties. Use `update_layers()` to control whether a layer appears in the legend.

```python
# Control legend visibility (NOT part of FSL - use update_layers)
felt_python.update_layers(
    map_id=map_id,
    layer_params_list=[{
        "id": layer_id,
        "legend_visibility": "show"  # or "hide" to remove from legend
    }]
)
```

**Two separate systems:**
1. **FSL `legend` block** (via `update_layer_style`) - Controls how legend entries look (displayName)
2. **Layer `legend_visibility`** (via `update_layers`) - Controls whether layer appears in legend at all

---

### Attributes Block

Customize attribute display names in popups and attribute tables.

```json
{
  "attributes": {
    "ele": {"displayName": "Elevation (meters)"},
    "faa": {"displayName": "FAA Code"},
    "temp_c": {"displayName": "Temperature (°C)"}
  }
}
```

---

### Popup Configuration

Control how feature information displays when users click on features.

**Basic popup:**

```json
{
  "popup": {
    "titleAttribute": "name",
    "imageAttribute": "photo_url",
    "keyAttributes": ["population", "area", "elevation"],
    "popupLayout": "table"  // or "list"
  }
}
```

**Popup location - control where popup appears:**

```json
{
  "popup": {
    "titleAttribute": "name",
    "keyAttributes": ["population", "state"],
    "popupLocation": "rightSidebar"  // "onMap", "leftSidebar", "rightSidebar", or "modal"
  }
}
```

**IFrame popups - embed external content:**

Static URL:
```json
{
  "popup": {
    "type": "iframe",
    "url": "https://example.com/details.html",
    "popupLocation": "modal",
    "width": 600,
    "height": 800
  }
}
```

Dynamic URL with templates:
```json
{
  "popup": {
    "type": "iframe",
    "url": "https://en.wikipedia.org/wiki/{{page_name}}",  // Simple attribute
    "popupLocation": "modal"
  }
}
```

For attributes with spaces, use array syntax:
```json
{
  "popup": {
    "type": "iframe",
    "url": "https://example.com/view?id={{feature_id}}&name={{['City Name']}}",
    "popupLocation": "rightSidebar"
  }
}
```

**Template syntax:**
- `{{attribute_name}}` - for simple attribute names
- `{{['Attribute Name']}}` - for attributes with spaces or special characters

---

### Filter Configuration

Filter which features display based on attribute values.

**Filter operators:**
- `lt` - Less than
- `gt` - Greater than
- `le` - Less than or equal to
- `ge` - Greater than or equal to
- `eq` - Equal to
- `ne` - Not equal to
- `and` - Logical AND
- `or` - Logical OR
- `bw` - Between (exclusive)
- `bwe` - Between (inclusive)
- `cn` - Contains (string)

**Filter syntax:**

```json
["attribute_name", "operator", value]
```

**Examples:**

```json
// Single condition
["population", "gt", 100000]

// Multiple conditions with AND
[["population", "gt", 100000], "and", ["state", "eq", "California"]]

// Multiple conditions with OR
[["type", "eq", "park"], "or", ["type", "eq", "recreation"]]

// Between range (exclusive)
["temperature", "bw", [0, 100]]

// Between range (inclusive)
["temperature", "bwe", [0, 100]]

// Contains text
["name", "cn", "Park"]
```

---

### Decision Tables

#### Which Viz Type Should I Use?

| Your Data | Use This | Why |
|-----------|----------|-----|
| No attribute styling needed | `simple` | Uniform appearance |
| Categories (land use, type) | `categorical` | Style by discrete groups |
| String categories preferred | `categorical` | Clear category names |
| Numeric values | `numeric` | Graduated colors/sizes |
| Numeric but want discrete buckets | `numeric` with manual steps | Better than categorical for numbers |
| Point density | `heatmap` | Shows clustering |
| Hex grid aggregation | `h3` | Spatial binning |
| Elevation/terrain | `hillshade` | 3D effect |

---

### Icon Reference

Use built-in icons or emojis instead of circles for point features.

**Icon Properties:**

- `iconImage`: Icon name (e.g., "star", "car") or emoji with prefix (e.g., "emoji:🚗")
- `iconFrame`: Frame around icon - "frame-circle" (default), "frame-square", "none"
- `iconHideOnZoom`: Zoom level to hide icon and show circle instead

**Note:** When using icons, the `size` property controls icon size, and `color` controls icon fill color. All point defaults still apply (see [Paint Properties by Geometry Type](#paint-properties-by-geometry-type)).

**Example with icon:**
```json
{
  "version": "2.3.1",
  "type": "simple",
  "paint": {
    "iconImage": "star",
    "color": "hsl(45,100%,50%)",
    "size": 4,
    "opacity": 0.9,
    "strokeColor": "auto",
    "strokeWidth": 1
  }
}
```

**Available Icons:**

Over 100 built-in icons available.

**Common icons:**

*Shapes:* `dot`, `square`, `diamond`, `triangle`, `x`, `plus`, `circle-line`, `star`, `heart`, `hexagon`, `octagon`

*Transportation:* `pedestrian`, `bicycle`, `wheelchair`, `airport`, `car`, `bus`, `train`, `truck`, `ferry`, `sailboat`, `traffic-light`, `road-sign-caution`

*Places:* `house`, `work`, `hotel`, `hospital`, `school`, `university`, `bank`, `museum`, `shopping`, `store`, `cafe`, `restaurant`, `park`, `camping-tent`

*Nature:* `tree`, `flower`, `leaf`, `fire`, `mountain`, `volcano`, `wave`, `water`, `lake`, `ocean`, `animal`, `bird`, `fish`, `beach`

*Weather:* `sun`, `moon`, `cloud`, `rain`, `lightning`, `snowflake`, `wind`, `fog`, `hurricane`

*Infrastructure:* `zap`, `battery-full`, `wind-turbine`, `solar-panel`, `antenna`, `wifi`, `trash`, `recycle`

*Signs:* `warning`, `parking`, `info`, `circle-exclamation`

**Emoji support:**
Prefix emojis with `"emoji:"`:
```json
{"iconImage": "emoji:🚗"}
{"iconImage": "emoji:🏠"}
{"iconImage": "emoji:🌟"}
```

---

### Common Mistakes & How to Avoid Them

#### ❌ Using `size` on polygons
```json
// WRONG - polygons don't have size property
{"paint": {"size": 5}}
```
✅ **Fix:** Use `strokeWidth` for polygon borders
```json
{"paint": {"strokeWidth": 2, "strokeColor": "#000"}}
```

---

#### ❌ Confusing line and point `size`
```json
// Point: size = radius (10 = 20px diameter)
{"paint": {"size": 10}}  // 10px radius circle

// Line: size = width (10 = 10px wide line)
{"paint": {"size": 10}}  // 10px wide line
```
✅ **Remember:** Same property, different meanings by geometry

---

#### ❌ Using "equal" instead of "equal-intervals"
```json
// WRONG
{"steps": {"type": "equal", "count": 5}}
```
✅ **Fix:**
```json
{"steps": {"type": "equal-intervals", "count": 5}}
```

---

#### ❌ Mismatched array lengths
```json
// WRONG - 3 breaks but 4 colors (3 breaks = 2 classes)
{
  "steps": [0, 50, 100],
  "color": ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"]
}
```
✅ **Fix:** N breaks = N-1 classes = N-1 colors
```json
{
  "steps": [0, 50, 100],
  "color": ["#FF0000", "#00FF00"]  // 2 colors for 2 classes
}
```

---

### Complete Example

This example demonstrates multiple FSL features working together:

```json
{
  "version": "2.3.1",
  "type": "numeric",
  "config": {
    "numericAttribute": "population",
    "steps": {"type": "jenks", "count": 5},
    "labelAttribute": ["city_name"]
  },
  "paint": {
    "color": "@galaxy",
    "opacity": 0.8,
    "strokeColor": "auto",
    "strokeWidth": 1,
    "size": [5, 40]
  },
  "label": {
    "color": "auto",
    "fontSize": 13,
    "haloColor": "auto",
    "haloWidth": 2,
    "minZoom": 8,
    "placement": "auto"
  },
  "legend": {
    "displayName": "City Population"
  },
  "attributes": {
    "population": {"displayName": "Population (2024)"},
    "city_name": {"displayName": "City Name"}
  }
}
```

This creates:
- Graduated symbol map (size by population)
- 5 color classes using Jenks classification
- City name labels visible at zoom level 8+
- Customized legend and attribute names

## Working with Layers

Manage layer properties after creation.

**Update layer metadata:**
```python
felt_python.update_layers(
    map_id=map_id,
    layer_params_list=[{
        "id": layer_id,
        "name": "New Layer Name",
        "caption": "Subtitle for legend",
        "ordering_key": 100,
        "legend_visibility": "show",
        "refresh_period": "hour"  # Auto-refresh from URL
    }]
)
```

**Update map properties:**
```python
felt_python.update_map(
    map_id=map_id,
    title="Updated Title",
    basemap="satellite",
    public_access="view_and_comment"
)
```

**Delete layer:**
```python
felt_python.delete_layer(map_id, layer_id)
```

**Refresh layer data:**
```python
felt_python.refresh_url_layer(map_id, layer_id)  # For URL uploads
felt_python.refresh_file_layer(map_id, layer_id, file_name)  # For file uploads
```

## Working with Elements

Add lightweight annotations (pins, markers, notes, paths) that sit above your data layers.

**Add elements:**
```python
felt_python.post_elements(
    map_id=map_id,
    geojson_feature_collection={
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-122.4194, 37.7749]},
            "properties": {
                "name": "Important Location",
                "felt:type": "Place",
                "felt:color": "#FF0000",
                "felt:symbol": "star"
            }
        }]
    }
)
```

**List and delete elements:**
```python
elements = felt_python.list_elements(map_id)
felt_python.delete_element(map_id, element_id)
```

**Styling elements:**

When updating elements, preserve ALL existing properties using `copy.deepcopy()`:

```python
import felt_python
import copy

# Fetch elements
elements = felt_python.list_elements(map_id=map_id)

# Modify elements
modified_features = []
for feature in elements['features']:
    modified = copy.deepcopy(feature)  # Preserve all properties

    if modified['properties'].get('felt:type') == 'Place':
        modified['properties']['felt:color'] = "#00FF00"
        modified['properties']['felt:symbol'] = "star"

    modified_features.append(modified)

# Update elements
felt_python.upsert_elements(
    map_id=map_id,
    geojson_feature_collection={
        "type": "FeatureCollection",
        "features": modified_features
    }
)
```

**Element types:**
- **Place** (Point) - Pins with `felt:color`, `felt:symbol`, `felt:icon`
- **Path** (MultiLineString) - Lines with `felt:color`, `felt:strokeWidth`, `felt:strokeStyle`
- **Marker** (MultiLineString) - Line markers with `felt:color`, `felt:size`
- **Link** (Polygon) - Link previews with `felt:color`, `felt:showLinkPreview`

## Elements (Annotations)

**What are Elements:**
- Lightweight GIS features (formerly called "Elements" in API, now "Annotations" in UI)
- Live at the top layer of maps, above all data layers
- Best for: Pins, highlights, markers, notes, text labels (< 100 features)
- Export as GeoJSON FeatureCollections

**When to use Elements vs Layers:**
- **Use Elements:** Quick annotations, location markers, lightweight markings (< 100 features)
- **Use Layers:** Data-heavy visualizations, large datasets, complex FSL styling

**Important practices:**
- **Always use `copy.deepcopy()`** before modifying elements to preserve all properties (API replaces ALL properties on update)
- **Prefer Pins** for location marking - they have the best styling support
- **Use Paths** for lines/routes - full styling control available

### Creating and Updating Elements

Elements are managed using GeoJSON FeatureCollections:

```python
from felt_python import post_elements, upsert_elements

# Create new pin
geojson = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [-122.4194, 37.7749]
            },
            "properties": {
                "name": "San Francisco",
                "felt:type": "Place",
                "felt:color": "#FF0000",
                "felt:symbol": "star"
            }
        }
    ]
}

response = post_elements(
    map_id="map-abc123",
    geojson_feature_collection=geojson
)
```

**Key property:** Include `"felt:id"` in properties to update existing elements. Without it, new elements are created.

### Styling Elements

**CRITICAL: When updating elements, you MUST preserve ALL existing properties.** The API replaces all properties with what you send. If you only send `felt:id` and `felt:color`, you'll lose all other properties (like `felt:type`, `felt:symbol`) and break the element.

**Always use `copy.deepcopy()` before modifying:**

```python
import felt_python
import copy

# Fetch elements
elements = felt_python.list_elements(map_id="map-abc123")

# Modify elements
modified_features = []
for feature in elements['features']:
    # Deep copy preserves ALL properties
    modified = copy.deepcopy(feature)

    # Now modify specific properties
    if modified['properties'].get('felt:type') == 'Place':
        modified['properties']['felt:color'] = "#00FF00"
        modified['properties']['felt:symbol'] = "star"

    modified_features.append(modified)

# Update all elements
felt_python.upsert_elements(
    map_id="map-abc123",
    geojson_feature_collection={
        "type": "FeatureCollection",
        "features": modified_features
    }
)
```

### Element Types and Styling Properties

#### Pin/Place Elements (Most Common)

**Geometry:** Point
**Type:** `felt:type` = "Place"

**Styling properties:**
- `felt:color` - Hex color (e.g., "#FF0000")
- `felt:symbol` - Built-in symbol ("star", "heart", "train", "dot", etc.)
- `felt:icon` - Emoji-style icon (":fire:", ":mountain:", ":star:")
- `name` - Pin label text
- `felt:isTextHidden` - Boolean to hide/show label

**Note:** Use EITHER `felt:symbol` OR `felt:icon`, not both. Setting one clears the other.

**Example:**
```python
# Change pin to green star with label
modified['properties']['felt:color'] = "#00FF00"
modified['properties']['felt:symbol'] = "star"
modified['properties']['name'] = "Important Location"
modified['properties']['felt:isTextHidden'] = False
```

#### Path/Line Elements

**Geometry:** MultiLineString
**Type:** `felt:type` = "Path"

**Styling properties:**
- `felt:color` - Hex color
- `felt:strokeWidth` - Width in pixels (integer)
- `felt:strokeStyle` - "solid", "dashed"
- `felt:strokeOpacity` - Opacity 0-1 (float)
- `felt:showLength` - Boolean to show length measurement

**Example:**
```python
# Style path as red dashed line
modified['properties']['felt:color'] = "#FF0000"
modified['properties']['felt:strokeWidth'] = 10
modified['properties']['felt:strokeStyle'] = "dashed"
modified['properties']['felt:strokeOpacity'] = 0.8
```

#### Marker Elements

**Geometry:** MultiLineString (rendered as line with marker symbols)
**Type:** `felt:type` = "Marker"

**Styling properties:**
- `felt:color` - Hex color
- `felt:size` - Size in pixels (integer)

**Example:**
```python
# Style marker as blue, size 20
modified['properties']['felt:color'] = "#0000FF"
modified['properties']['felt:size'] = 20
```

#### Link Elements

**Geometry:** Polygon (bounding box for link preview)
**Type:** `felt:type` = "Link"

**Styling properties:**
- `felt:color` - Border/accent color
- `felt:showLinkPreview` - Boolean to show preview
- `name` - Link title (required)
- `description` - Link description (required)

**Example:**
```python
# Change link color
modified['properties']['felt:color'] = "#800080"
modified['properties']['felt:showLinkPreview'] = True
# Must preserve name, description, felt:mapLinkId
```

#### Text and Note Elements

**Type:** `felt:type` = "Text" or "Note"

**Warning:** Text and Note elements have limited API support. When updated via API, they lose most styling properties (scale, rotation, textStyle, position). Only `felt:color` can be reliably changed.

**Recommendation:** Modify Text/Note elements through the Felt UI, not the API.

### Listing and Deleting Elements

```python
from felt_python import list_elements, delete_element

# List all elements
elements = list_elements(map_id="map-abc123")

for feature in elements['features']:
    props = feature['properties']
    element_id = props.get('felt:id')
    element_type = props.get('felt:type')
    name = props.get('name', 'Unnamed')
    print(f"{element_type}: {name} ({element_id})")

# Delete specific element
delete_element(
    map_id="map-abc123",
    element_id="element-xyz789"
)
```

# FINDING DATA

When users need GIS data, recommend these sources based on their needs:

## Felt Library Layers

Felt maintains a library of 50+ ready-to-use layers that can supplement custom data uploads. These layers are pre-styled and can be added directly to maps without downloading.

**Access via Python:**

```python
import felt_python

# List available Felt library layers
library = felt_python.list_library_layers(source="felt")

# Add a library layer to your map
felt_python.duplicate_layers([{
    "source_map_id": "library_map_id",      # From library layer
    "source_layer_id": "layer_id",          # From library layer
    "destination_map_id": "your_map_id"
}])
```

**Available Categories (53 layers):**
- Basins & Watersheds (HydroBASINS)
- Bicycle Lanes (OpenStreetMap)
- Buildings (Maptiler)
- California/Hawaii State Parks & Trails
- Earthquakes (USGS)
- Ferry Routes & Terminals
- Graticules (Natural Earth grid lines)
- Hospitals & Clinics
- Hydrothermal Features
- Intact Forest Landscapes
- National Flood Hazard Layer (FEMA)
- NYC Subway System
- Railway Tracks & Stations
- School Districts (US Census)
- Terrain (Contours, Hillshade)
- Trails, Tracks & Footways
- US Bureau of Land Management lands
- US Electric Power Transmission Lines
- US Forest Service lands
- US National Parks

**Best for:** Adding supplementary context layers to custom data, US infrastructure/recreation mapping.

## Cloud Sources

**IMPORTANT:** Cloud Sources are only available to Enterprise plan customers. This section covers USING existing sources that have been set up (not creating/configuring them).

Sources are live connections to cloud databases, cloud storage, and web services. Once connected by admins, data becomes available as a catalog of layers that can be added to maps.

**Using sources to add data to maps:**

```python
from felt_python import list_sources, get_source, add_source_layer

# List available sources in your workspace
sources = list_sources()
for source in sources:
    print(f"{source['name']} ({source['connection_type']})")

# Get source details to see available datasets
source = get_source(source_id="source-abc123")
for dataset in source['datasets']:
    print(f"  - {dataset['name']} ({dataset['geometry_type']})")

# Add dataset as a layer to your map
response = add_source_layer(
    map_id="map-xyz789",
    source_layer_params={
        "from": "dataset",
        "dataset_id": dataset['id']
    }
)
```

**Example: Add layer from SQL query**

**CRITICAL:** Always include `ST_Transform(geom, 4326)` in SQL queries to convert geometry to WGS 84 (EPSG:4326), which is required by Felt.

```python
from felt_python import add_source_layer

# Execute SQL query against a database source
sql = """
SELECT
    id,
    name,
    ST_Transform(geom, 4326) as geometry,  -- Required transformation
    population
FROM cities
WHERE population > 100000
"""

response = add_source_layer(
    map_id="map-xyz789",
    source_layer_params={
        "from": "sql",
        "source_id": "source-abc123",
        "query": sql
    }
)
```

**SQL requirements:**
- Read-only (SELECT only)
- Include geometry column transformed to EPSG:4326
- Supported databases: PostGIS, Snowflake, BigQuery, SQL Server, Databricks, Redshift

**Common spatial operations:** `ST_Transform()`, `ST_Intersects()`, `ST_Buffer()`, `ST_Distance()`, `ST_Area()`, `ST_Centroid()`, `ST_Union()`

**Live syncing:**
- Layers from sources auto-refresh based on configured frequency
- Sources scanned every 24 hours for schema changes
- Check `sync_status` is "completed" before adding layers from new sources

**Best for:** Enterprise users with data in cloud databases/storage who need live syncing, SQL filtering, or programmatic access to organizational data sources.

## Global Vector Data

**Natural Earth Data** (naturalearth.com)
- Public domain global datasets
- Available at 1:10m, 1:50m, 1:110m scales
- Formats: SHP, SQLite, GeoPackage
- Best for: Country boundaries, physical features, cultural data

**OpenStreetMap** (openstreetmap.org)
- Crowdsourced, highly detailed data
- HOT Export Tool for custom extracts
- Formats: SHP, GeoPackage, KML, PBF, MBTiles
- Best for: Roads, buildings, POIs, any urban features

## Government Sources

**USGS National Map** (usgs.gov/programs/national-geospatial-program)
- Elevation, hydrography, boundaries, transportation
- Best for: US-focused projects

**US Census Bureau** (census.gov/geographies)
- TIGER/Line shapefiles
- Administrative boundaries, demographics
- Best for: US demographic mapping

## Administrative Boundaries

**GADM** (gadm.org)
- Global administrative boundaries
- Up to 4 levels of detail
- Formats: SHP, RDS, KML, GeoPackage
- Best for: Country/state/province boundaries

**DIVA-GIS** (diva-gis.org)
- Country-by-country downloads
- Administrative and environmental data
- Best for: Quick country data

## Open Data Portals

**Esri Open Data Hub** (hub.arcgis.com)
- 250,000+ datasets from 5,000+ organizations
- Multiple format options
- Best for: Finding specific thematic data

**Google Earth Engine** (earthengine.google.com)
- Satellite imagery and analysis
- Free for academic/research use
- Best for: Remote sensing, large-scale analysis

## Other Resources

**Free GIS Data** (freegisdata.rtwilson.com)
- Categorized list of free GIS data sources
- Regularly updated

**GitHub awesome-geospatial-data-sources**
- Curated list of open geospatial data
- Community maintained

# CARTOGRAPHIC GUIDANCE

## Design Principles

**Think like a cartographer first, then implement.** Choosing the wrong visualization type is the #1 source of misleading maps.

### Choosing the Right Visualization Type

Match your **data type** to the correct **map type**:

```
CATEGORICAL DATA (types/kinds: land use, species, political party)
├─ Points → Categorical with icons/colors
├─ Polygons → Categorical choropleth
└─ FSL: type: "categorical"

ORDINAL DATA (ranked/ordered: Low/Medium/High, risk levels)
├─ Points → Graduated symbols (size variation)
├─ Polygons → Sequential choropleth
└─ FSL: type: "numeric" with manual steps

QUANTITATIVE DATA (numeric measurements)
├─ Is it a RATE or DENSITY? (per sq km, percentage, ratio)
│   └─ Yes → Choropleth ✓
├─ Is it a RAW COUNT or TOTAL? (population, sales, incidents)
│   └─ Yes → Proportional symbols (NOT choropleth!)
├─ Point density to show?
│   └─ Heatmap (type: "heatmap")
├─ Point values to aggregate?
│   └─ H3 hexbin (type: "h3")
└─ Two variables at once?
    └─ Bivariate (size + color with paintPropertyOverrides)
```

### Choropleth Maps: Rates vs Counts

**Critical distinction:** Choropleth maps (filled polygons) should only be used for rates/densities, never raw counts.

**Why:** Large geographic areas always look "important" regardless of actual rate. A state with 1M people across 10,000 sq km looks identical to one with 1M people in 100 sq km.

```json
// ❌ WRONG: Raw count choropleth
{
  "type": "numeric",
  "config": {"numericAttribute": "total_population"}
}

// ✓ RIGHT: Normalize to rate/density
{
  "type": "numeric",
  "config": {"numericAttribute": "pop_per_sq_km"}
}

// ✓ RIGHT: Use proportional symbols for counts
{
  "type": "numeric",
  "config": {"numericAttribute": "total_population", "steps": {"type": "continuous"}},
  "paint": {"size": [3, 30]}  // Size varies with value (default range)
}
```

**Rule:** If your data is "how many" (counts/totals), use proportional symbols. If it's "how much per unit" (rates/densities), use choropleth.

### Choosing the Right Color Palette

Match palette type to data structure:

| Data Type | Palette Type | Felt Palettes | Use When |
|-----------|--------------|---------------|----------|
| **Sequential** (low→high, one direction) | Sequential | `@galaxy`, `@ylRed`, `@riverine`, `@neptune`, `@lightning` | Income, density, temperature (all positive/negative) |
| **Diverging** (meaningful midpoint) | Diverging | `@bluRd`, `@tealOr`, `@grnOr`, `@purGrn` | Change from baseline, above/below average, +/− values |
| **Categorical** (unordered types) | Categorical | `@catPalette1` through `@catPalette7` | Land use types, species, facility types |
| **Heatmaps** | Thermal | `@thermal`, `@purpYlPink` | Point density visualization |

**Rules:**
1. **Sequential** - Light→dark. One direction only.
2. **Diverging** - Two hues from neutral center. Midpoint MUST align with data midpoint (usually 0).
3. **Categorical** - Equally prominent colors. No hierarchy.
4. **Colorblind safe** - Avoid red-green; use blue-orange for diverging.

```json
// Diverging: change from baseline
{"config": {"numericAttribute": "pct_change", "steps": [-50, -25, 0, 25, 50]}, "paint": {"color": "@bluRd"}}

// Sequential: low to high
{"paint": {"color": "@galaxy"}}
```

### Visual Hierarchy

Control attention: Primary (saturated/large) → Secondary (muted/small) → Basemap (minimal)

```python
create_map(basemap="light")  # Muted basemap

# Primary: saturated
{"paint": {"color": "#DC2626", "size": 16, "opacity": 1.0}}

# Secondary: muted
{"paint": {"color": "#9CA3AF", "size": 8, "opacity": 0.6}}
```

Basemap selection: `"light"` (default), `"dark"` (bright data), `"satellite"` (rarely)

### Classification Methods

How you break continuous values into classes changes the map's message.

| Method | Best For | FSL Config |
|--------|----------|------------|
| **Jenks** | Default choice, finds natural groupings | `{"type": "jenks", "count": 5}` |
| **Quantiles** | Equal visual balance (same # features per class) | `{"type": "quantiles", "count": 5}` |
| **Equal Interval** | When ranges matter more than distribution | `{"type": "equal-intervals", "count": 5}` |
| **Manual** | Specific meaningful thresholds (policy limits, etc.) | `[0, 10, 50, 100, 500]` |
| **Continuous** | Smooth gradient, no discrete classes | `{"type": "continuous"}` |

**General rule:** 4-7 classes. Fewer than 4 oversimplifies; more than 7 exceeds human perception limits.

```json
// Jenks: Let data speak (default choice)
{"steps": {"type": "jenks", "count": 5}}

// Manual: Policy-relevant breaks
{"steps": [0, 4, 5, 6, 7, 9]}  // Earthquake magnitude thresholds
```

**Always ask:** "Why these break points?" If you can't explain, reconsider your classification.
