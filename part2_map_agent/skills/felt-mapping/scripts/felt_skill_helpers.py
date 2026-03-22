"""
Helper functions for working with felt-python.

Usage:
    import skill
    skill.load_api_key_from_env()
    skill.wait_for_layer_processing(map_id, layer_id, timeout_s=30)
    skill.inspect_created_map(map_id)
"""

import os
import time
import felt_python


def load_api_key_from_env():
    """
    Load Felt API token from .env file and set as environment variable.

    The .env file should contain: FELT_API_TOKEN=your_token_here

    Returns:
        str: The API token if found, None otherwise

    Example:
        >>> import skill
        >>> skill.load_api_key_from_env()
        >>> # API token now available to felt_python functions
    """
    if not os.path.exists('.env'):
        print("Warning: .env file not found")
        return None

    with open('.env', 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('FELT_API_TOKEN='):
                api_key = line.split('=', 1)[1].strip()
                os.environ['FELT_API_TOKEN'] = api_key
                print("✓ Felt API token loaded from .env")
                return api_key

    print("Warning: FELT_API_TOKEN not found in .env file")
    return None


def wait_for_layer_processing(map_id, layer_id, timeout_s=30):
    """
    Wait for a layer to finish processing after upload.

    Returns the complete layer object including attributes metadata.
    Use the returned attributes to inform FSL styling decisions.

    Args:
        map_id: The map ID
        layer_id: The layer ID to wait for
        timeout_s: Maximum time to wait in seconds (default: 30)
                   Note: Larger datasets may need more time (60-300s)

    Returns:
        dict: The layer metadata when processing completes, including:
            - status: 'completed' when done
            - attributes: List of {"name": str, "type": str} dicts
                         Types: INTEGER, REAL, TEXT, BOOLEAN, DATE, DATETIME, GEOMETRY
            - name, caption, ordering_key, created_at, updated_at, etc.

    Raises:
        Exception: If layer processing fails
        TimeoutError: If processing doesn't complete within timeout

    Example:
        >>> import skill
        >>> from felt_python import upload_url
        >>>
        >>> upload = upload_url(map_id="map-123", layer_url="https://example.com/data.geojson")
        >>> layer = skill.wait_for_layer_processing(map_id="map-123", layer_id=upload['layer_id'])
        >>>
        >>> # For larger datasets, increase timeout:
        >>> layer = skill.wait_for_layer_processing(map_id, layer_id, timeout_s=120)
    """
    elapsed = 0
    poll_interval = 1  # Fixed 1 second polling

    while elapsed < timeout_s:
        layer = felt_python.get_layer(map_id=map_id, layer_id=layer_id)
        status = layer.get('status')

        if status == 'completed':
            print(f"✓ Layer processing completed ({elapsed}s)")
            return layer
        elif status == 'failed':
            error_msg = layer.get('error', 'Unknown error')
            raise Exception(f"Layer processing failed: {error_msg}")

        time.sleep(poll_interval)
        elapsed += poll_interval

    raise TimeoutError(f"Layer processing timed out after {timeout_s}s (status: {status})")


def inspect_created_map(map_id, api_token=None):
    """
    Inspect a map and display all information needed for styling.

    Call this after creating and uploading data to a map. It fetches
    and displays the map URL, all layers, and their attributes.

    **IMPORTANT:** This function automatically writes map and layer IDs
    to 'context.json' for later retrieval. Read this file with bash later
    to get IDs back into context if needed.

    Args:
        map_id: The map ID to inspect
        api_token: Optional API token (uses env var if not provided)

    Returns:
        dict: Map info with layers

    Example:
        >>> import skill
        >>> skill.load_api_key_from_env()
        >>> map_id = "map-abc123"  # from create_map()
        >>> skill.inspect_created_map(map_id)

        === Map Context ===
        {
          "map_id": "map-abc123",
          "map_name": "Earthquake Analysis",
          "map_url": "https://felt.com/map/earthquake-analysis-abc123",
          "layers": [
            {
              "layer_id": "layer-xyz789",
              "layer_name": "Earthquakes",
              "status": "completed",
              "attributes": [
                {"name": "mag", "type": "REAL"},
                {"name": "depth", "type": "REAL"},
                {"name": "place", "type": "TEXT"}
              ],
              "style": {
                "version": "2.3.1",
                "type": "simple",
                "paint": {"color": "#808080"}
              }
            }
          ]
        }

        ✓ Context saved to context.json
    """
    import json

    # Get map info
    map_info = felt_python.get_map(map_id=map_id, api_token=api_token)
    map_url = map_info['url']
    map_title = map_info.get('title', 'Untitled Map')

    # Get all layers
    layers = felt_python.list_layers(map_id=map_id, api_token=api_token)

    # Build comprehensive context structure
    context = {
        "map_id": map_id,
        "map_name": map_title,
        "map_url": map_url,
        "layers": []
    }

    if layers:
        for layer in layers:
            layer_id = layer['id']
            layer_name = layer.get('name', 'Unnamed')
            status = layer.get('status', 'unknown')

            layer_context = {
                "layer_id": layer_id,
                "layer_name": layer_name,
                "status": status
            }

            # Get full layer details for completed layers
            if status == 'completed':
                layer_details = felt_python.get_layer(map_id=map_id, layer_id=layer_id, api_token=api_token)

                # Add attributes
                layer_context["attributes"] = layer_details.get('attributes', [])

                # Add current style
                layer_context["style"] = layer_details.get('style', {})

            context['layers'].append(layer_context)

    # Pretty-print context to console (this goes into context window)
    print("\n=== Map Context ===")
    print(json.dumps(context, indent=2))

    # Write to file
    with open('context.json', 'w') as f:
        json.dump(context, f, indent=2)
    print("\n✓ Context saved to context.json")

    return {'map': map_info, 'layers': layers}
