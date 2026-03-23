from felt_python import create_map, add_source_layer, update_layer_style
from felt_helpers import wait_for_layer, numeric_style
import os

TOKEN = os.environ["FELT_API_TOKEN"]
SOURCE_ID = os.environ["FELT_SOURCE_ID"]

# Create map
m = create_map(title="Air Quality Index", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]

# Add AQI data
params = {
    "from": "sql",
    "source_id": SOURCE_ID,
    "query": "SELECT * FROM public.airnow_air_quality_index"
}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)

# Wait and style
layer = wait_for_layer(map_id)
style = numeric_style("gridcode", palette="@ylRed")
update_layer_style(map_id=map_id, layer_id=layer["id"], style=style, api_token=TOKEN)

print(f"Map: {map_url}")
