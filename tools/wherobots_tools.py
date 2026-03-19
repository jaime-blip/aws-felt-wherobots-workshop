"""
Wherobots MCP Tools
====================

Strands @tool wrappers around Wherobots Cloud (Apache Sedona).
These let an AI agent run spatial SQL queries, load satellite data,
and compute risk scores — all via natural language.
"""

import os
import json
import logging
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely import wkt
from strands import tool

logger = logging.getLogger(__name__)

# ── Wherobots connection singleton ────────────────────────────────

_conn = None


def _get_connection():
    """Get or create a Wherobots connection."""
    global _conn
    if _conn is not None:
        return _conn

    from wherobots.db import connect, Region, Runtime

    api_key = os.environ.get("WHEROBOTS_API_KEY")
    if not api_key:
        raise RuntimeError("WHEROBOTS_API_KEY not set")

    logger.info("Connecting to Wherobots Cloud...")
    _conn = connect(
        host="api.cloud.wherobots.com",
        api_key=api_key,
        runtime=Runtime.TINY,
        region=Region.AWS_US_WEST_2,
    )
    logger.info("Connected to Wherobots!")
    return _conn


# ── Tools ─────────────────────────────────────────────────────────


@tool
def wherobots_query(sql: str) -> dict:
    """Run a spatial SQL query on Wherobots Cloud (Apache Sedona).

    Use this to query geospatial datasets: building footprints, satellite
    imagery, weather data, or any spatial table in the Wherobots catalog.

    Common tables:
    - wherobots_open_data.overture.buildings_building (global building footprints)
    - wherobots_open_data.overture.places_place (POIs)
    - wherobots_open_data.overture.transportation_segment (roads)

    Useful Sedona functions:
    - ST_Point(lon, lat) — create point
    - ST_GeomFromWKT(wkt) — parse WKT geometry
    - ST_Distance(g1, g2) — distance between geometries
    - ST_Within(g1, g2) — containment test
    - ST_Intersects(g1, g2) — intersection test
    - ST_Buffer(geom, dist) — buffer geometry
    - ST_Area(geom) — compute area

    Args:
        sql: Spatial SQL query to execute on Sedona.

    Returns:
        dict with columns, rows, and row_count.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []

        # Convert to serializable format
        clean_rows = []
        for row in rows[:500]:  # cap at 500
            clean_row = []
            for val in row:
                if hasattr(val, "wkt"):
                    clean_row.append(val.wkt)
                else:
                    clean_row.append(val)
            clean_rows.append(clean_row)

        return {
            "columns": columns,
            "rows": clean_rows,
            "row_count": len(rows),
            "truncated": len(rows) > 500,
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def wherobots_count_buildings(south: float, west: float, north: float, east: float) -> dict:
    """Count Overture Maps building footprints in a bounding box.

    Use this to quickly check how many buildings are in an area before
    running expensive spatial joins.

    Args:
        south: Southern latitude of bounding box.
        west: Western longitude of bounding box.
        north: Northern latitude of bounding box.
        east: Eastern longitude of bounding box.

    Returns:
        dict with building count.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        bbox_wkt = f"POLYGON(({west} {south}, {east} {south}, {east} {north}, {west} {north}, {west} {south}))"
        cursor.execute(f"""
            SELECT COUNT(*) as cnt
            FROM wherobots_open_data.overture.buildings_building
            WHERE ST_Within(geometry, ST_GeomFromWKT('{bbox_wkt}'))
        """)
        count = cursor.fetchone()[0]
        return {"building_count": count, "bbox": {"south": south, "west": west, "north": north, "east": east}}
    except Exception as e:
        return {"error": str(e)}


@tool
def wherobots_explore_catalog(schema: str = "overture") -> dict:
    """List available tables in a Wherobots catalog schema.

    Use this to discover what datasets are available for querying.

    Args:
        schema: Schema name to explore. Default: 'overture'.
            Options: overture, nasa, noaa, etc.

    Returns:
        dict with list of table names.
    """
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(f"SHOW TABLES IN wherobots_open_data.{schema}")
        tables = [row[0] for row in cursor.fetchall()]
        return {"schema": schema, "tables": tables}
    except Exception as e:
        return {"error": str(e)}


@tool
def load_risk_data(city: str = "") -> dict:
    """Load pre-computed climate risk data for buildings.

    This loads the enriched building dataset from the data engineering
    pipeline (Half 1). Each building has flood, storm, wildfire, and
    composite risk scores.

    Available cities: Houston, Los Angeles, Miami.
    Leave city empty to load all.

    Args:
        city: Filter by city name. Empty string for all cities.

    Returns:
        dict with risk data summary and sample records.
    """
    try:
        data_path = Path(__file__).parent.parent / "data" / "risk_scored_buildings.geojson"
        if not data_path.exists():
            return {"error": f"Risk data not found at {data_path}. Run notebooks/05_export_results.py first."}

        gdf = gpd.read_file(data_path)
        if city:
            gdf = gdf[gdf.city.str.lower() == city.lower()]
            if len(gdf) == 0:
                return {"error": f"No data for city '{city}'. Available: Houston, Los Angeles, Miami"}

        summary = {
            "total_buildings": len(gdf),
            "cities": gdf.city.unique().tolist(),
            "risk_distribution": gdf.risk_category.value_counts().to_dict(),
            "avg_composite_risk": round(gdf.composite_risk.mean(), 3),
            "max_composite_risk": round(gdf.composite_risk.max(), 3),
            "sample_records": json.loads(gdf.head(5).to_json()),
        }
        return summary
    except Exception as e:
        return {"error": str(e)}
