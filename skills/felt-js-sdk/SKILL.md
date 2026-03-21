---
name: felt-js-sdk
description: Guide for building interactive map applications with the Felt JavaScript SDK. Use this skill when users want to embed Felt maps, control map viewport, add/remove layers, draw annotations, handle selections, filter data, or build custom map UIs. Triggers on mentions of Felt, Felt SDK, Felt maps, or embedded mapping applications.
---

# Felt JavaScript SDK

Build interactive map applications by embedding and controlling Felt maps programmatically.

## Installation & Setup

```bash
npm install @feltmaps/js-sdk
```

### Embedding a Map

```javascript
import { Felt } from "@feltmaps/js-sdk";

const felt = await Felt.embed(
  document.getElementById("map-container"),
  "FELT_MAP_ID"
);
```

### Connecting to Existing Iframe

```javascript
const felt = await Felt.connect(iframe.contentWindow);
```

Find the map ID in Map Settings > Developers, or extract from the URL after the title.

## Core Concepts

- All methods are async and return Promises
- Singular getters: `getLayer(id)` returns entity or `null`
- Plural getters: `getLayers()` or `getLayers({ ids: [...] })` with constraints
- Change listeners: `on{Entity}Change()` returns unsubscribe function — always clean up

## Viewport Control

```javascript
// Get current viewport
const { center, zoom } = await felt.getViewport();

// Set viewport
await felt.setViewport({ center: { lat: 37.78, lng: -122.42 }, zoom: 12 });

// Fit to bounds
await felt.fitViewportToBounds({ west: -122.5, south: 37.7, east: -122.3, north: 37.9 });

// Listen to changes
const unsub = felt.onViewportMove({ handler: ({ center, zoom }) => {} });
```

## Reading Entities

```javascript
// Single entity
const layer = await felt.getLayer("layer-id");

// Multiple with constraints
const elements = await felt.getElements({ ids: ["el-1", "el-2"] });
const legendItems = await felt.getLegendItems({ layerIds: ["layer-1"] });

// All entities
const allLayers = await felt.getLayers();

// Listen for changes
const unsub = felt.onLayerChange({
  options: { id: "layer-1" },
  handler: ({ layer }) => {}
});
```

## Layers

### Create from GeoJSON

```javascript
const result = await felt.createLayersFromGeoJson({
  source: {
    type: "geoJsonUrl",
    url: "https://example.com/data.geojson"
  },
  name: "My Layer",
  caption: "Optional caption",
  refreshInterval: 60000, // auto-refresh (250ms to 5min)
  geometryStyles: {
    Point: { color: "#FF0000", size: 10 },
    Polygon: { color: "#00FF00", fillOpacity: 0.5 }
  }
});
// Returns { layerGroup, layers }
```

Source types: `geoJsonUrl`, `geoJsonFile` (File object), `geoJsonData` (GeoJSON object)

**Note:** SDK-created layers are session-specific and don't support filtering/statistics.

### Manage Layers

```javascript
await felt.deleteLayer("layer-id");  // SDK-created only
await felt.updateLayer({ id: "layer-id", source: { ... } });
```

## Visibility Control

```javascript
// Layers
await felt.setLayerVisibility({ show: ["layer-1"], hide: ["layer-2"] });

// Layer groups
await felt.setLayerGroupVisibility({ show: ["group-1"] });

// Legend items
await felt.setLegendItemVisibility({
  show: [{ layerId: "layer-1", id: "item-1" }],
  hide: [{ layerId: "layer-1", id: "item-2" }]
});
```

## Layer Filters

```javascript
// Get all filters (style, components, ephemeral, combined)
const filters = await felt.getLayerFilters("layer-id");

// Set ephemeral filter
await felt.setLayerFilters({
  layerId: "layer-id",
  filters: ["POPULATION", "gt", 1000000]
});

// Compound filter
await felt.setLayerFilters({
  layerId: "layer-id",
  filters: [
    ["POPULATION", "gt", 1000000],
    "and",
    ["COUNTRY", "eq", "USA"]
  ]
});

// Clear filters
await felt.setLayerFilters({ layerId: "layer-id", filters: null });
```

Operators: `lt`, `gt`, `le`, `ge`, `eq`, `ne`, `cn` (contains), `nc`, `in`, `ni`, `and`, `or`

## Drawing Annotations

### Interactive Tools

```javascript
// Configure and activate tool
felt.setToolSettings({ tool: "polygon", strokeWidth: 4, color: "#448C2A" });
felt.setTool("polygon");
felt.setTool(null); // deactivate

// Available tools
const tool = await felt.getTool();
const settings = await felt.getToolSettings();
```

Tools: `pin`, `line`, `route`, `polygon`, `circle`, `marker`, `highlighter`, `text`, `note`

### Programmatic Creation

```javascript
const element = await felt.createElement({
  type: "Polygon",
  coordinates: [[[-122.42, 37.78], [-122.41, 37.78], [-122.41, 37.77], [-122.42, 37.77], [-122.42, 37.78]]],
  color: "#FF5733",
  fillOpacity: 0.5
});

await felt.updateElement({ id: element.id, type: "Polygon", color: "#ABC123" });
await felt.deleteElement(element.id);

// Get GeoJSON geometry
const geom = await felt.getElementGeometry(element.id);
```

### Element Events

```javascript
felt.onElementCreate({ handler: (element) => {} });
felt.onElementCreateEnd({ handler: ({ element }) => {} }); // tool drawing complete
felt.onElementChange({ handler: (element) => {} });
felt.onElementDelete({ handler: (element) => {} });
```

**Note:** SDK-created annotations are session-specific and not visible to other users.

## Selection

```javascript
// Select feature
await felt.selectFeature({
  id: "feature-123",
  layerId: "layer-id",
  showPopup: true,
  fitViewport: { maxZoom: 15 }
});

// Get selection (returns EntityNode array)
const selection = await felt.getSelection();

// Clear selection
await felt.clearSelection({ features: true, elements: false });

// Listen
const unsub = felt.onSelectionChange({ handler: ({ selection }) => {} });
```

Only one feature can be selected at a time.

## Map Interactions

```javascript
// Click events
const unsub = felt.onPointerClick({
  handler: ({ center, features, point, rasterValues }) => {}
});

// Hover events (throttle for performance)
felt.onPointerMove({
  handler: throttle(({ center, features }) => {}, 100)
});
```

## Data Analysis

```javascript
// Aggregates (count, sum, average)
const stats = await felt.getAggregates({ layerId: "layer-id", method: "sum", attribute: "population" });

// Category data
const categories = await felt.getCategoryData({ layerId: "layer-id", attribute: "type" });

// Histogram
const histogram = await felt.getHistogramData({ layerId: "layer-id", attribute: "value" });
```

## UI Components (Extensions)

```javascript
// Action trigger (sidebar button)
felt.createActionTrigger({ label: "Run Analysis", onTrigger: () => {} });

// Custom panel
const panelId = felt.createPanelId();
felt.createOrUpdatePanel({
  id: panelId,
  header: { title: "Settings", onClickClose: () => felt.deletePanel(panelId) },
  body: [
    { type: "Text", content: "Configure options:" },
    { type: "TextInput", id: "name-input", placeholder: "Name", onChange: (v) => {} },
    { type: "Select", id: "type-select", options: [...], value: "a", onChange: (v) => {} }
  ],
  footer: {
    type: "ButtonRow",
    items: [{ label: "Save", variant: "filled", onClick: () => {} }]
  }
});
```

Element types: `Text`, `TextInput`, `Select`, `CheckboxGroup`, `RadioGroup`, `ToggleGroup`, `Button`, `ButtonRow`, `Grid`, `Iframe`, `Divider`

## React Integration

```javascript
// Custom hook pattern
function useFeltEmbed(mapId, options) {
  const [felt, setFelt] = useState(null);
  const containerRef = useRef(null);
  const mountedRef = useRef(false);

  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;

    Felt.embed(containerRef.current, mapId, options).then(setFelt);
  }, [mapId]);

  return { felt, containerRef };
}

// Live entity updates
function useLiveLayer(felt, layerId) {
  const [layer, setLayer] = useState(null);

  useEffect(() => {
    if (!felt) return;
    felt.getLayer(layerId).then(setLayer);
    return felt.onLayerChange({
      options: { id: layerId },
      handler: ({ layer }) => setLayer(layer)
    });
  }, [felt, layerId]);

  return layer;
}
```

Starter template: https://github.com/felt/js-sdk-starter-react
