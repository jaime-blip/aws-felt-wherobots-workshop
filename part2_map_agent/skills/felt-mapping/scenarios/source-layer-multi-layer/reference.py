from felt_python import create_map, add_source_layer, update_layer_style
from felt_helpers import wait_for_layer, categorical_style, resolve_source_id
import os

TOKEN = os.environ["FELT_API_TOKEN"]
SOURCE_ID = resolve_source_id()

# Create map
m = create_map(title="Wildfires & National Parks", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]

# Layer 1: Wildfire perimeters by category
params = {
    "from": "sql",
    "source_id": SOURCE_ID,
    "query": "SELECT * FROM public.wildfire_perimeters"
}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)
layer = wait_for_layer(map_id)
style = categorical_style("poly_featurecategory", top_n=5)
update_layer_style(map_id=map_id, layer_id=layer["id"], style=style, api_token=TOKEN)

# Layer 2: National parks by region
params = {
    "from": "sql",
    "source_id": SOURCE_ID,
    "query": "SELECT * FROM public.federal_lands_national_parks"
}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)
layer = wait_for_layer(map_id)
style = categorical_style("region", top_n=10)
update_layer_style(map_id=map_id, layer_id=layer["id"], style=style, api_token=TOKEN)

print(f"Map: {map_url}")
