#!/usr/bin/env python3
"""
Step 5: Export Results
=======================

Export the enriched, risk-scored building data so the Strands agent
(Half 2) can load it and visualize on Felt maps.

We'll export as both GeoJSON and Parquet.
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, Polygon
from shapely import wkt

load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# ── For the workshop, generate sample enriched data locally ───────
# In production, this would query the risk_scored_buildings view
# from Step 4 and export via Wherobots.

print("📦 Generating sample enriched dataset for the agent...\n")

import random
random.seed(42)

# Houston flood risk buildings
houston_buildings = []
for i in range(200):
    lat = 29.60 + random.uniform(0, 0.25)
    lon = -95.55 + random.uniform(0, 0.25)
    flood_score = random.uniform(0, 1)
    storm_score = random.uniform(0, 0.8)
    composite = 0.4 * flood_score + 0.3 * storm_score + 0.3 * random.uniform(0, 0.2)

    if composite >= 0.5:
        category = "critical"
    elif composite >= 0.3:
        category = "high"
    elif composite >= 0.15:
        category = "moderate"
    else:
        category = "low"

    houston_buildings.append({
        "building_id": f"houston_{i:04d}",
        "geometry": Point(lon, lat),
        "flood_risk": round(flood_score, 3),
        "storm_risk": round(storm_score, 3),
        "wildfire_risk": round(random.uniform(0, 0.1), 3),
        "composite_risk": round(composite, 3),
        "risk_category": category,
        "city": "Houston",
    })

# LA wildfire risk buildings
la_buildings = []
for i in range(200):
    lat = 33.95 + random.uniform(0, 0.30)
    lon = -118.70 + random.uniform(0, 0.55)
    wildfire_score = random.uniform(0.2, 1.0)
    storm_score = random.uniform(0, 0.3)
    flood_score = random.uniform(0, 0.2)
    composite = 0.3 * wildfire_score + 0.3 * storm_score + 0.4 * flood_score

    if composite >= 0.5:
        category = "critical"
    elif composite >= 0.3:
        category = "high"
    elif composite >= 0.15:
        category = "moderate"
    else:
        category = "low"

    la_buildings.append({
        "building_id": f"la_{i:04d}",
        "geometry": Point(lon, lat),
        "flood_risk": round(flood_score, 3),
        "storm_risk": round(storm_score, 3),
        "wildfire_risk": round(wildfire_score, 3),
        "composite_risk": round(composite, 3),
        "risk_category": category,
        "city": "Los Angeles",
    })

# Miami flood + storm risk
miami_buildings = []
for i in range(200):
    lat = 25.70 + random.uniform(0, 0.20)
    lon = -80.30 + random.uniform(0, 0.20)
    flood_score = random.uniform(0.3, 1.0)
    storm_score = random.uniform(0.2, 0.9)
    composite = 0.4 * flood_score + 0.3 * storm_score + 0.3 * random.uniform(0, 0.15)

    if composite >= 0.5:
        category = "critical"
    elif composite >= 0.3:
        category = "high"
    elif composite >= 0.15:
        category = "moderate"
    else:
        category = "low"

    miami_buildings.append({
        "building_id": f"miami_{i:04d}",
        "geometry": Point(lon, lat),
        "flood_risk": round(flood_score, 3),
        "storm_risk": round(storm_score, 3),
        "wildfire_risk": round(random.uniform(0, 0.05), 3),
        "composite_risk": round(composite, 3),
        "risk_category": category,
        "city": "Miami",
    })

# Combine all
all_buildings = houston_buildings + la_buildings + miami_buildings
gdf = gpd.GeoDataFrame(all_buildings, geometry="geometry", crs="EPSG:4326")

# ── Export GeoJSON ────────────────────────────────────────────────

geojson_path = DATA_DIR / "risk_scored_buildings.geojson"
gdf.to_file(geojson_path, driver="GeoJSON")
print(f"✅ GeoJSON: {geojson_path} ({len(gdf)} buildings)")

# ── Export Parquet ────────────────────────────────────────────────

parquet_path = DATA_DIR / "risk_scored_buildings.parquet"
gdf.to_parquet(parquet_path)
print(f"✅ Parquet: {parquet_path}")

# ── Summary stats ─────────────────────────────────────────────────

print(f"\n📊 Dataset summary:")
print(f"   Total buildings: {len(gdf)}")
for city in ["Houston", "Los Angeles", "Miami"]:
    subset = gdf[gdf.city == city]
    print(f"\n   {city}:")
    for cat in ["critical", "high", "moderate", "low"]:
        count = len(subset[subset.risk_category == cat])
        print(f"     • {cat}: {count} buildings")

print(f"\n✅ Step 5 complete! Data exported to {DATA_DIR}/")
print("   Ready for Half 2: building the Strands agent!")
