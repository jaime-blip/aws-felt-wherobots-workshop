#!/usr/bin/env python3
"""
Step 5: Export Gold Layer → Amazon Aurora PostgreSQL
=====================================================

Export the scored building data from Wherobots to Aurora PostgreSQL
via JDBC. Aurora + PostGIS gives us a fast, SQL-queryable spatial
database that the Strands agent can query in Part 2.

Two export approaches shown:
  A) Wherobots JDBC write (direct Sedona → Aurora)
  B) Local export via GeoDataFrame → SQLAlchemy/psycopg2 (fallback)
"""

import os
from pathlib import Path
from dotenv import load_dotenv
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
from sqlalchemy import create_engine, text

load_dotenv()

AURORA_HOST = os.environ.get("AURORA_HOST", "localhost")
AURORA_PORT = os.environ.get("AURORA_PORT", "5432")
AURORA_DB = os.environ.get("AURORA_DB", "workshop")
AURORA_USER = os.environ.get("AURORA_USER", "postgres")
AURORA_PASSWORD = os.environ.get("AURORA_PASSWORD", "")

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

print("=" * 60)
print("  EXPORT — Gold Layer → Aurora PostgreSQL")
print("=" * 60)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Approach A: Wherobots JDBC Write (production)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("""
📌 Approach A: Wherobots JDBC Export (Production)

In production, Sedona writes directly to Aurora via JDBC:

    -- In Wherobots / Sedona SQL:
    CREATE TABLE aurora_export
    USING jdbc
    OPTIONS (
        url 'jdbc:postgresql://{host}:5432/{db}',
        dbtable 'public.building_risk',
        user '{user}',
        password '{password}',
        driver 'org.postgresql.Driver'
    )
    AS SELECT * FROM gold_building_risk;

This pushes data directly from the Sedona cluster to Aurora
without going through a local machine. Fast and scalable.
""")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Approach B: Local GeoDataFrame → Aurora (workshop fallback)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("📌 Approach B: Local export via GeoDataFrame (workshop)\n")

# Generate sample gold data locally (same as what Wherobots would produce)
import random
random.seed(42)

buildings = []
cities = {
    "Austin":      {"lat": (30.15, 30.35), "lon": (-97.90, -97.60), "fire_bias": 0.6, "flood_bias": 0.4},
    "Houston":     {"lat": (29.60, 29.85), "lon": (-95.55, -95.30), "fire_bias": 0.1, "flood_bias": 0.8},
    "Miami":       {"lat": (25.70, 25.90), "lon": (-80.30, -80.10), "fire_bias": 0.05, "flood_bias": 0.7},
    "Los Angeles": {"lat": (33.95, 34.25), "lon": (-118.70, -118.15), "fire_bias": 0.85, "flood_bias": 0.15},
}

for city, cfg in cities.items():
    for i in range(250):
        lat = random.uniform(*cfg["lat"])
        lon = random.uniform(*cfg["lon"])
        flood = random.uniform(0, cfg["flood_bias"])
        storm = random.uniform(0, 0.6)
        fire = random.uniform(0, cfg["fire_bias"])
        composite = round(0.4 * flood + 0.3 * storm + 0.3 * fire, 3)

        if composite >= 0.6: cat = "critical"
        elif composite >= 0.35: cat = "high"
        elif composite >= 0.15: cat = "moderate"
        else: cat = "low"

        dominant = max([("flood", flood), ("storm", storm), ("wildfire", fire)], key=lambda x: x[1])[0]

        buildings.append({
            "building_id": f"{city.lower().replace(' ', '_')}_{i:04d}",
            "geometry": Point(lon, lat),
            "city": city,
            "flood_risk": round(flood, 3),
            "storm_risk": round(storm, 3),
            "wildfire_risk": round(fire, 3),
            "composite_risk": composite,
            "risk_category": cat,
            "dominant_hazard": dominant,
        })

gdf = gpd.GeoDataFrame(buildings, geometry="geometry", crs="EPSG:4326")

# Save local copy
geojson_path = DATA_DIR / "gold_building_risk.geojson"
gdf.to_file(geojson_path, driver="GeoJSON")
print(f"💾 Local GeoJSON: {geojson_path} ({len(gdf)} buildings)")

parquet_path = DATA_DIR / "gold_building_risk.parquet"
gdf.to_parquet(parquet_path)
print(f"💾 Local Parquet: {parquet_path}")

# ── Write to Aurora PostgreSQL ────────────────────────────────────

if AURORA_PASSWORD:
    print(f"\n🐘 Writing to Aurora PostgreSQL: {AURORA_HOST}/{AURORA_DB}...")

    engine = create_engine(
        f"postgresql://{AURORA_USER}:{AURORA_PASSWORD}@{AURORA_HOST}:{AURORA_PORT}/{AURORA_DB}"
    )

    with engine.connect() as conn:
        # Enable PostGIS
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        conn.commit()

        # Drop and recreate table
        conn.execute(text("DROP TABLE IF EXISTS building_risk"))
        conn.commit()

    # Write GeoDataFrame to PostGIS
    gdf.to_postgis(
        name="building_risk",
        con=engine,
        if_exists="replace",
        index=False,
    )

    # Verify
    with engine.connect() as conn:
        result = conn.execute(text("SELECT COUNT(*) FROM building_risk"))
        count = result.scalar()
        print(f"   ✅ Wrote {count:,} buildings to Aurora")

        # Create spatial index
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_building_risk_geom
            ON building_risk USING GIST (geometry)
        """))
        conn.commit()
        print("   ✅ Spatial index created")

        # Quick test query
        result = conn.execute(text("""
            SELECT city, risk_category, COUNT(*)
            FROM building_risk
            GROUP BY city, risk_category
            ORDER BY city, COUNT(*) DESC
        """))
        print("\n   📊 Aurora table summary:")
        for row in result:
            print(f"     {row[0]:15s} | {row[1]:10s} | {row[2]:,}")
else:
    print("\n⚠️  AURORA_PASSWORD not set — skipping Aurora export.")
    print("   Set credentials in .env to enable JDBC export.")
    print("   The local GeoJSON/Parquet files can be used as fallback.")

print("\n" + "=" * 60)
print("  ✅ EXPORT COMPLETE")
print("  Gold layer is in Aurora PostgreSQL (or local files).")
print("  Ready for Part 2 → Building the Map Agent!")
print("=" * 60)
