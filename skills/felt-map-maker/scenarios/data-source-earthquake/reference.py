import sys
sys.path.insert(0, '/path/to/skill/scripts')
import skill

from felt_python import create_map, upload_url, update_layer_style

# Load API key
skill.load_api_key_from_env()

# Stage 1: Create map and upload earthquake data
map_response = create_map(title="Recent Earthquakes")
map_id = map_response['id']

layer_response = upload_url(
    map_id=map_id,
    layer_url="https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_month.geojson",
    layer_name="Earthquakes - Last 30 Days"
)
layer_id = layer_response['layer_id']

# Wait for processing and inspect
skill.wait_for_layer_processing(map_id=map_id, layer_id=layer_id)
skill.inspect_created_map(map_id=map_id)

# Stage 2: Apply styling
fsl_style = {
    "version": "2.3.1",
    "type": "numeric",
    "config": {
        "numericAttribute": "mag",
        "steps": {"type": "quantiles", "count": 5}
    },
    "paint": {
        "color": "@thermal"
    }
}

update_layer_style(map_id=map_id, layer_id=layer_id, style=fsl_style)
