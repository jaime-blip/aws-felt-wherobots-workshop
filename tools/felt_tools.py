"""
Felt MCP Tools
===============

Strands @tool wrappers for Felt's mapping API.
Create maps, upload data, apply styles — all from natural language.

These tools + skills give the agent full cartographic capability:
the agent can take risk data from Aurora and turn it into
publication-ready interactive maps in seconds.
"""

import os
import json
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from strands import tool

from felt_python import (
    create_map,
    upload_geodataframe,
    update_layer_style,
)

logger = logging.getLogger(__name__)


# ── Map Creation ──────────────────────────────────────────────────


@tool
def create_felt_map(title: str, lat: float = 0.0, lon: float = 0.0, zoom: int = 10) -> dict:
    """Create a new interactive Felt map.

    Use this when the user wants to visualize data on a map.
    Returns a map URL that can be shared.

    Args:
        title: Map title (e.g., "Austin Wildfire Risk").
        lat: Center latitude.
        lon: Center longitude.
        zoom: Zoom level 1-20.

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


# ── Data Upload ───────────────────────────────────────────────────


@tool
def upload_buildings_to_map(map_id: str, buildings: list, layer_name: str = "Buildings") -> dict:
    """Upload a list of buildings (from Aurora query) to a Felt map.

    Takes the buildings list returned by get_buildings_in_area or
    query_aurora and uploads them as a point layer.

    Each building dict should have at minimum: lon, lat.
    Additional fields (risk scores, category) become layer attributes.

    Args:
        map_id: Felt map ID to upload to.
        buildings: List of building dicts with lon, lat, and risk fields.
        layer_name: Name for the layer.

    Returns:
        dict with layer_id and count.
    """
    try:
        if not buildings:
            return {"error": "No buildings to upload"}

        rows = []
        for b in buildings:
            row = {k: v for k, v in b.items() if k not in ("geometry", "lon", "lat")}
            row["geometry"] = Point(float(b["lon"]), float(b["lat"]))
            rows.append(row)

        gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")

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
def upload_geojson_to_map(map_id: str, file_path: str, layer_name: str) -> dict:
    """Upload a GeoJSON file to a Felt map.

    Use this to add the full gold layer GeoJSON to a map.

    Args:
        map_id: Felt map ID.
        file_path: Path to GeoJSON file.
        layer_name: Layer display name.

    Returns:
        dict with layer_id.
    """
    try:
        gdf = gpd.read_file(file_path)
        result = upload_geodataframe(
            map_id=map_id,
            geodataframe=gdf,
            layer_name=layer_name,
        )
        return {
            "layer_id": result.get("layer_id"),
            "feature_count": len(gdf),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Styling ───────────────────────────────────────────────────────


@tool
def style_by_risk_category(map_id: str, layer_id: str) -> dict:
    """Style a layer by risk category using red/orange/yellow/green.

    Applies categorical coloring:
      🔴 critical → 🟠 high → 🟡 moderate → 🟢 low

    Use this after uploading buildings to make the risk levels
    immediately visible on the map.

    Args:
        map_id: Felt map ID.
        layer_id: Layer ID to style.

    Returns:
        dict confirming style applied.
    """
    try:
        style = {
            "version": "2.3.1",
            "type": "categorical",
            "config": {
                "labelAttribute": "risk_category",
                "showOther": True,
                "categories": [
                    {"value": "critical", "color": "#DC2626", "label": "Critical"},
                    {"value": "high", "color": "#F97316", "label": "High"},
                    {"value": "moderate", "color": "#EAB308", "label": "Moderate"},
                    {"value": "low", "color": "#22C55E", "label": "Low"},
                ],
            },
            "paint": {
                "color": "auto",
                "size": 6,
                "strokeWidth": 1,
                "strokeColor": "auto",
            },
        }
        update_layer_style(map_id=map_id, layer_id=layer_id, style=style)
        return {"success": True, "style": "categorical_risk", "legend": "🔴 critical → 🟠 high → 🟡 moderate → 🟢 low"}
    except Exception as e:
        return {"error": str(e)}


@tool
def style_by_numeric_risk(map_id: str, layer_id: str, attribute: str = "composite_risk") -> dict:
    """Style a layer with a gradient based on a numeric risk score.

    Creates a green→red gradient visualization. Good for showing
    the continuous risk spectrum rather than just categories.

    Attribute options: composite_risk, flood_risk, storm_risk, wildfire_risk.

    Args:
        map_id: Felt map ID.
        layer_id: Layer ID to style.
        attribute: Numeric column to color by. Default: composite_risk.

    Returns:
        dict confirming style applied.
    """
    try:
        style = {
            "version": "2.3.1",
            "type": "numeric",
            "config": {
                "numericAttribute": attribute,
                "steps": 5,
                "label": attribute.replace("_", " ").title(),
            },
            "paint": {
                "color": ["#22C55E", "#84CC16", "#EAB308", "#F97316", "#DC2626"],
                "size": 6,
                "strokeWidth": 1,
                "strokeColor": "auto",
            },
        }
        update_layer_style(map_id=map_id, layer_id=layer_id, style=style)
        return {"success": True, "style": f"numeric_gradient({attribute})"}
    except Exception as e:
        return {"error": str(e)}
