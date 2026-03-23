from felt_python import create_map, add_source_layer, update_layer_style
from felt_helpers import wait_for_layer
import os

TOKEN = os.environ["FELT_API_TOKEN"]
SOURCE_ID = os.environ["FELT_SOURCE_ID"]

# Create map
m = create_map(title="Smoke Density", api_token=TOKEN)
map_id, map_url = m["id"], m["url"]

# Add smoke density data
params = {
    "from": "sql",
    "source_id": SOURCE_ID,
    "query": "SELECT * FROM public.smoke_density"
}
add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)

# Wait and style
layer = wait_for_layer(map_id)

style = {
    "version": "2.3.1",
    "type": "categorical",
    "config": {
        "categoricalAttribute": "density",
        "categories": ["Light", "Medium", "Heavy"],
        "showOther": True
    },
    "paint": {
        "color": ["#fde68a", "#f97316", "#991b1b"],
        "opacity": 0.5,
        "strokeColor": "auto",
        "strokeWidth": 1
    },
    "legend": {
        "displayName": {
            "Light": "Light Smoke",
            "Medium": "Medium Smoke",
            "Heavy": "Heavy Smoke"
        }
    }
}
update_layer_style(map_id=map_id, layer_id=layer["id"], style=style, api_token=TOKEN)

print(f"Map: {map_url}")
