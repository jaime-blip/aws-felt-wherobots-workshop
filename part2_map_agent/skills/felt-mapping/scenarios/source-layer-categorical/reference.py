from felt_python import create_map, add_source_layer, update_layer_style
from felt_helpers import wait_for_layer, categorical_style
import os

TOKEN = os.environ["FELT_API_TOKEN"]
SOURCE_ID = os.environ["FELT_SOURCE_ID"]

# Create map
m = create_map(title="Wildfire Locations by Cause", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]

# Add SQL source layer
params = {
    "from": "sql",
    "source_id": SOURCE_ID,
    "query": "SELECT * FROM public.wildfire_locations"
}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)

# Wait for processing
layer = wait_for_layer(map_id)
layer_id = layer["id"]

# Style by fire cause
style = categorical_style("firecausegeneral", top_n=10)
update_layer_style(map_id=map_id, layer_id=layer_id, style=style, api_token=TOKEN)

print(f"Map: {map_url}")
