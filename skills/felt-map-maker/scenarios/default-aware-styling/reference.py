import sys
sys.path.insert(0, '/path/to/skill/scripts')
import skill

from felt_python import update_layer_style

# Load API key
skill.load_api_key_from_env()

# Context from previous map creation shows existing style with multiple properties
map_id = "map-test123"
layer_id = "layer-abc789"

# Update style: change color to blue, retain all other properties
fsl_style = {
    "version": "2.3.1",
    "type": "simple",
    "paint": {
        "color": "#3B82F6",
        "opacity": 0.75,
        "size": 8,
        "stroke": "#333333",
        "strokeWidth": 1.5,
        "strokeOpacity": 0.9
    },
    "label": {
        "text": ["name"],
        "placement": "point",
        "offset": [0, 2]
    }
}

update_layer_style(map_id=map_id, layer_id=layer_id, style=fsl_style)
