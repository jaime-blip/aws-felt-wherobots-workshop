"""
Felt MCP Tools
===============

Strands @tool wrappers for Felt's mapping API.
Creates interactive maps, uploads geospatial data, and styles layers.

Felt is an AI-native collaborative mapping platform.
These tools let an AI agent create publication-ready maps from data.
"""

import os
import json
import logging
from pathlib import Path

import geopandas as gpd
from strands import tool

from felt_python import (
    create_map,
    upload_geodataframe,
    upload_file,
    update_layer_style,
    get_map,
    list_layers,
)

logger = logging.getLogger(__name__)


@tool
def create_felt_map(title: str, lat: float = 0.0, lon: float = 0.0, zoom: int = 10) -> dict:
    """Create a new interactive Felt map.

    Use this when you want to visualize geospatial data. Creates a blank
    map centered on the given coordinates.

    Args:
        title: Map title (e.g., "Houston Flood Risk Assessment").
        lat: Center latitude. Default 0.
        lon: Center longitude. Default 0.
        zoom: Initial zoom level 1-20. Default 10.

    Returns:
        dict with map_id and map_url.
    """
    try:
        response = create_map(
            title=title,
            lat=lat,
            lon=lon,
            zoom=zoom,
            public_access="private",
        )
        return {
            "map_id": response["id"],
            "map_url": response["url"],
            "title": title,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def upload_geojson_to_felt(map_id: str, file_path: str, layer_name: str) -> dict:
    """Upload a GeoJSON file to a Felt map as a new layer.

    Use this to add data layers from GeoJSON files produced by the
    data engineering pipeline.

    Args:
        map_id: Felt map ID to upload to.
        file_path: Path to the GeoJSON file.
        layer_name: Display name for the layer on the map.

    Returns:
        dict with layer_id and feature count.
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        gdf = gpd.read_file(path)
        result = upload_geodataframe(
            map_id=map_id,
            geodataframe=gdf,
            layer_name=layer_name,
        )
        return {
            "layer_id": result.get("layer_id"),
            "feature_count": len(gdf),
            "layer_name": layer_name,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def upload_risk_data_to_felt(map_id: str, city: str, layer_name: str = "") -> dict:
    """Upload pre-computed risk-scored building data to a Felt map.

    Loads the enriched building dataset from the data pipeline and
    uploads it as a styled layer. Optionally filter by city.

    Available cities: Houston, Los Angeles, Miami.

    Args:
        map_id: Felt map ID to upload to.
        city: City to filter by (Houston, Los Angeles, Miami). Empty for all.
        layer_name: Layer name. Auto-generated if empty.

    Returns:
        dict with layer_id and upload details.
    """
    try:
        data_path = Path(__file__).parent.parent / "data" / "risk_scored_buildings.geojson"
        if not data_path.exists():
            return {"error": "Risk data not found. Run notebooks/05_export_results.py first."}

        gdf = gpd.read_file(data_path)
        if city:
            gdf = gdf[gdf.city.str.lower() == city.lower()]
            if len(gdf) == 0:
                return {"error": f"No data for '{city}'. Available: Houston, Los Angeles, Miami"}

        if not layer_name:
            layer_name = f"Climate Risk — {city}" if city else "Climate Risk — All Cities"

        result = upload_geodataframe(
            map_id=map_id,
            geodataframe=gdf,
            layer_name=layer_name,
        )
        return {
            "layer_id": result.get("layer_id"),
            "feature_count": len(gdf),
            "layer_name": layer_name,
            "risk_distribution": gdf.risk_category.value_counts().to_dict(),
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def style_risk_layer(map_id: str, layer_id: str) -> dict:
    """Apply climate risk color styling to a layer on a Felt map.

    Colors buildings by risk category:
    - Critical (red), High (orange), Moderate (yellow), Low (green)

    Uses Felt Style Language (FSL) for categorical styling.

    Args:
        map_id: Felt map ID.
        layer_id: Layer ID to style.

    Returns:
        dict confirming style was applied.
    """
    try:
        # FSL categorical style based on risk_category
        style = {
            "version": "2.3.1",
            "type": "categorical",
            "config": {
                "labelAttribute": "risk_category",
                "showOther": True,
                "categories": [
                    {
                        "value": "critical",
                        "color": "#DC2626",
                        "label": "Critical Risk",
                    },
                    {
                        "value": "high",
                        "color": "#F97316",
                        "label": "High Risk",
                    },
                    {
                        "value": "moderate",
                        "color": "#EAB308",
                        "label": "Moderate Risk",
                    },
                    {
                        "value": "low",
                        "color": "#22C55E",
                        "label": "Low Risk",
                    },
                ],
            },
            "paint": {
                "color": "auto",
                "size": 6,
                "strokeWidth": 1,
                "strokeColor": "auto",
            },
        }

        update_layer_style(
            map_id=map_id,
            layer_id=layer_id,
            style=style,
        )
        return {"success": True, "style": "risk_categorical", "colors": "🔴 critical → 🟠 high → 🟡 moderate → 🟢 low"}
    except Exception as e:
        return {"error": str(e)}


@tool
def style_numeric_layer(map_id: str, layer_id: str, attribute: str, label: str = "") -> dict:
    """Apply a numeric gradient style to a layer based on an attribute.

    Good for visualizing continuous risk scores (composite_risk, flood_risk, etc.)
    as a color gradient from green (low) to red (high).

    Args:
        map_id: Felt map ID.
        layer_id: Layer ID to style.
        attribute: Numeric attribute to style by (e.g., 'composite_risk', 'flood_risk').
        label: Legend label. Defaults to attribute name.

    Returns:
        dict confirming style was applied.
    """
    try:
        style = {
            "version": "2.3.1",
            "type": "numeric",
            "config": {
                "numericAttribute": attribute,
                "steps": 5,
                "label": label or attribute,
            },
            "paint": {
                "color": ["#22C55E", "#84CC16", "#EAB308", "#F97316", "#DC2626"],
                "size": 6,
                "strokeWidth": 1,
                "strokeColor": "auto",
            },
        }

        update_layer_style(
            map_id=map_id,
            layer_id=layer_id,
            style=style,
        )
        return {"success": True, "style": f"numeric_gradient on '{attribute}'"}
    except Exception as e:
        return {"error": str(e)}
