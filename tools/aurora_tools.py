"""
Aurora PostGIS Tools
=====================

Strands @tool wrappers for querying Amazon Aurora PostgreSQL with PostGIS.

The gold layer (building risk scores) lives in Aurora. These tools let
the agent run spatial SQL queries to find at-risk buildings, filter by
location, and get risk summaries for any area.
"""

import os
import json
import logging

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from strands import tool

logger = logging.getLogger(__name__)

_engine = None


def _get_engine():
    """Get or create SQLAlchemy engine for Aurora PostgreSQL."""
    global _engine
    if _engine is not None:
        return _engine

    host = os.environ.get("AURORA_HOST", "localhost")
    port = os.environ.get("AURORA_PORT", "5432")
    db = os.environ.get("AURORA_DB", "workshop")
    user = os.environ.get("AURORA_USER", "postgres")
    password = os.environ.get("AURORA_PASSWORD", "")

    _engine = create_engine(f"postgresql://{user}:{password}@{host}:{port}/{db}")
    logger.info(f"Connected to Aurora: {host}/{db}")
    return _engine


def _fallback_geodataframe(city: str = ""):
    """Load from local GeoJSON if Aurora is not available."""
    from pathlib import Path
    data_path = Path(__file__).parent.parent / "data" / "gold_building_risk.geojson"
    if not data_path.exists():
        return None
    gdf = gpd.read_file(data_path)
    if city:
        gdf = gdf[gdf.city.str.lower() == city.lower()]
    return gdf


# ── Tools ─────────────────────────────────────────────────────────


@tool
def query_aurora(sql: str) -> dict:
    """Run a spatial SQL query on Aurora PostgreSQL (PostGIS).

    The building_risk table contains climate risk scores for buildings.
    Columns: building_id, geometry (Point), city, flood_risk, storm_risk,
    wildfire_risk, composite_risk, risk_category, dominant_hazard.

    PostGIS functions available:
    - ST_DWithin(geom, geom, meters) — within distance (use geography cast)
    - ST_Contains(polygon, point) — containment
    - ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326) — bounding box
    - ST_Distance(geom::geography, geom::geography) — distance in meters
    - ST_AsGeoJSON(geom) — geometry as GeoJSON
    - ST_X(geom), ST_Y(geom) — extract coordinates

    Args:
        sql: PostGIS SQL query to execute.

    Returns:
        dict with columns, rows, and row_count.
    """
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            columns = list(result.keys())
            rows = [list(row) for row in result.fetchall()]

            # Stringify any non-serializable values
            clean_rows = []
            for row in rows[:500]:
                clean_rows.append([str(v) if not isinstance(v, (int, float, str, bool, type(None))) else v for v in row])

            return {
                "columns": columns,
                "rows": clean_rows,
                "row_count": len(rows),
                "truncated": len(rows) > 500,
            }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_buildings_in_area(city: str = "", south: float = 0, west: float = 0, north: float = 0, east: float = 0, risk_category: str = "", limit: int = 100) -> dict:
    """Get risk-scored buildings from Aurora, filtered by location and risk.

    Use city name for quick filtering, or bounding box for custom areas.
    Returns buildings with their risk scores for mapping.

    Available cities: Austin, Houston, Miami, Los Angeles.

    Args:
        city: Filter by city name (e.g., 'Austin'). Overrides bbox if set.
        south: Southern latitude of bounding box.
        west: Western longitude of bounding box.
        north: Northern latitude of bounding box.
        east: Eastern longitude of bounding box.
        risk_category: Filter by risk level: critical, high, moderate, low. Empty for all.
        limit: Max buildings to return. Default 100.

    Returns:
        dict with buildings list and summary statistics.
    """
    try:
        conditions = ["1=1"]
        if city:
            conditions.append(f"city = '{city}'")
        elif south != 0 or west != 0:
            conditions.append(f"""
                ST_Contains(
                    ST_MakeEnvelope({west}, {south}, {east}, {north}, 4326),
                    geometry
                )
            """)
        if risk_category:
            conditions.append(f"risk_category = '{risk_category}'")

        where = " AND ".join(conditions)
        sql = f"""
            SELECT building_id, ST_X(geometry) as lon, ST_Y(geometry) as lat,
                   city, flood_risk, storm_risk, wildfire_risk,
                   composite_risk, risk_category, dominant_hazard
            FROM building_risk
            WHERE {where}
            ORDER BY composite_risk DESC
            LIMIT {limit}
        """

        try:
            engine = _get_engine()
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                rows = [dict(row._mapping) for row in result.fetchall()]

                # Summary
                summary_sql = f"""
                    SELECT COUNT(*) as total,
                           ROUND(AVG(composite_risk)::numeric, 3) as avg_risk,
                           ROUND(MAX(composite_risk)::numeric, 3) as max_risk,
                           SUM(CASE WHEN risk_category='critical' THEN 1 ELSE 0 END) as critical,
                           SUM(CASE WHEN risk_category='high' THEN 1 ELSE 0 END) as high,
                           SUM(CASE WHEN risk_category='moderate' THEN 1 ELSE 0 END) as moderate,
                           SUM(CASE WHEN risk_category='low' THEN 1 ELSE 0 END) as low
                    FROM building_risk WHERE {where}
                """
                summary = dict(conn.execute(text(summary_sql)).fetchone()._mapping)
        except Exception:
            # Fallback to local file
            gdf = _fallback_geodataframe(city)
            if gdf is None:
                return {"error": "Aurora unavailable and no local data. Run 05_export_aurora.py first."}
            if risk_category:
                gdf = gdf[gdf.risk_category == risk_category]
            gdf = gdf.nlargest(limit, "composite_risk")
            rows = json.loads(gdf.drop(columns="geometry").to_json(orient="records"))
            for r, geom in zip(rows, gdf.geometry):
                r["lon"] = geom.x
                r["lat"] = geom.y
            summary = {
                "total": len(gdf),
                "avg_risk": round(gdf.composite_risk.mean(), 3),
                "max_risk": round(gdf.composite_risk.max(), 3),
            }

        return {
            "buildings": rows,
            "summary": summary,
            "filters": {"city": city, "risk_category": risk_category},
        }
    except Exception as e:
        return {"error": str(e)}


@tool
def get_risk_summary(city: str = "") -> dict:
    """Get aggregate risk statistics for a city or all data.

    Quick overview of risk distribution without returning individual buildings.
    Good for answering "How risky is Houston?" type questions.

    Args:
        city: City name to summarize. Empty for all cities.

    Returns:
        dict with risk category counts, averages, and dominant hazards.
    """
    try:
        where = f"WHERE city = '{city}'" if city else ""

        try:
            engine = _get_engine()
            with engine.connect() as conn:
                result = conn.execute(text(f"""
                    SELECT
                        city,
                        risk_category,
                        COUNT(*) as buildings,
                        ROUND(AVG(composite_risk)::numeric, 3) as avg_composite,
                        ROUND(AVG(flood_risk)::numeric, 3) as avg_flood,
                        ROUND(AVG(storm_risk)::numeric, 3) as avg_storm,
                        ROUND(AVG(wildfire_risk)::numeric, 3) as avg_wildfire
                    FROM building_risk
                    {where}
                    GROUP BY city, risk_category
                    ORDER BY city, avg_composite DESC
                """))
                rows = [dict(r._mapping) for r in result.fetchall()]

                dominant = conn.execute(text(f"""
                    SELECT city, dominant_hazard, COUNT(*) as cnt
                    FROM building_risk {where}
                    GROUP BY city, dominant_hazard
                    ORDER BY city, cnt DESC
                """))
                hazard_rows = [dict(r._mapping) for r in dominant.fetchall()]
        except Exception:
            gdf = _fallback_geodataframe(city)
            if gdf is None:
                return {"error": "No data available."}
            rows = []
            for (c, rc), group in gdf.groupby(["city", "risk_category"]):
                rows.append({
                    "city": c, "risk_category": rc, "buildings": len(group),
                    "avg_composite": round(group.composite_risk.mean(), 3),
                    "avg_flood": round(group.flood_risk.mean(), 3),
                    "avg_storm": round(group.storm_risk.mean(), 3),
                    "avg_wildfire": round(group.wildfire_risk.mean(), 3),
                })
            hazard_rows = []

        return {"risk_by_city_category": rows, "dominant_hazards": hazard_rows}
    except Exception as e:
        return {"error": str(e)}
