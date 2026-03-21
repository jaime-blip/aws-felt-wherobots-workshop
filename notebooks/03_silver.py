#!/usr/bin/env python3
"""
Step 3: Silver Layer — Clean, Normalize, Spatial Joins
========================================================

SILVER = cleaned, validated, joined data. We:
  1. Filter low-confidence MODIS observations
  2. Normalize storm magnitudes to a 0-1 scale
  3. Spatial join: buildings × flood zones × storm events × wildfire zones
  4. Each building gets individual hazard exposure attributes
"""

import os
from dotenv import load_dotenv
from wherobots.db import connect, Region, Runtime

load_dotenv()

conn = connect(
    host="api.cloud.wherobots.com",
    api_key=os.environ["WHEROBOTS_API_KEY"],
    runtime=Runtime.TINY,
    region=Region.AWS_US_WEST_2,
)
cursor = conn.cursor()
print("✅ Connected to Wherobots\n")
print("=" * 60)
print("  SILVER LAYER — Clean, Normalize, Spatial Joins")
print("=" * 60)

# NOTE: Re-run 02_bronze.py first to create the temp views,
# or in production these would be persistent tables.

# ── Silver 1: Clean MODIS flood data ─────────────────────────────

print("\n🌊 [Silver] Cleaning MODIS flood data...")
print("   Filtering: confidence >= 0.85, depth > 0")

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW silver_flood AS
    SELECT
        id,
        geometry,
        flood_depth_m,
        -- Normalize depth to 0-1 (cap at 3m)
        LEAST(flood_depth_m / 3.0, 1.0) as flood_severity,
        acquisition_date,
        source
    FROM bronze_modis_flood
    WHERE confidence >= 0.85
      AND flood_depth_m > 0
""")

cursor.execute("SELECT COUNT(*), AVG(flood_severity) FROM silver_flood")
r = cursor.fetchone()
print(f"   ✅ {r[0]} flood zones passed QC | avg severity: {r[1]:.2f}")

# ── Silver 2: Normalize storm events ─────────────────────────────

print("\n⛈️  [Silver] Normalizing storm event magnitudes...")

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW silver_storms AS
    SELECT
        id,
        geometry,
        event_type,
        magnitude,
        magnitude_unit,
        event_date,
        -- Normalize each event type to 0-1 severity
        CASE
            WHEN event_type = 'hail' THEN LEAST(magnitude / 4.0, 1.0)
            WHEN event_type = 'tornado' THEN LEAST(magnitude / 5.0, 1.0)
            WHEN event_type = 'wind' THEN LEAST(magnitude / 130.0, 1.0)
            ELSE 0.5
        END as storm_severity,
        -- Impact radius in meters (for proximity scoring)
        CASE
            WHEN event_type = 'tornado' THEN 2000 * magnitude
            WHEN event_type = 'hail' THEN 5000
            WHEN event_type = 'wind' THEN 8000
            ELSE 3000
        END as impact_radius_m,
        source
    FROM bronze_noaa_storms
""")

cursor.execute("""
    SELECT event_type, COUNT(*), ROUND(AVG(storm_severity), 2)
    FROM silver_storms GROUP BY event_type
""")
print("   Normalized events:")
for row in cursor.fetchall():
    print(f"     • {row[0]}: {row[1]} events, avg severity: {row[2]}")

# ── Silver 3: Wildfire zones (already normalized) ─────────────────

print("\n🔥 [Silver] Wildfire zones (burn_probability already 0-1)...")

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW silver_wildfire AS
    SELECT
        id,
        geometry,
        burn_probability as wildfire_severity,
        flame_length_m,
        vegetation_type,
        source
    FROM bronze_usfs_wildfire
    WHERE burn_probability > 0.1  -- Filter out negligible risk
""")

cursor.execute("SELECT COUNT(*), AVG(wildfire_severity) FROM silver_wildfire")
r = cursor.fetchone()
print(f"   ✅ {r[0]} wildfire zones | avg severity: {r[1]:.2f}")

# ── Silver 4: Spatial Joins — Buildings × Hazards ─────────────────

print("\n🏗️  [Silver] Spatial joining buildings with all hazard layers...")
print("   This is the key step — enriching each building with hazard exposure.\n")

# Austin AOI for the workshop
AOI = "POLYGON((-97.90 30.15, -97.60 30.15, -97.60 30.35, -97.90 30.35, -97.90 30.15))"

cursor.execute(f"""
    CREATE OR REPLACE TEMP VIEW silver_buildings_hazards AS
    SELECT
        b.id as building_id,
        ST_X(ST_Centroid(b.geometry)) as lon,
        ST_Y(ST_Centroid(b.geometry)) as lat,
        b.geometry as building_geom,

        -- Flood exposure: max severity of overlapping flood zones
        COALESCE(MAX(f.flood_severity), 0) as flood_exposure,

        -- Storm exposure: max severity of nearby storm events
        COALESCE(MAX(s.storm_severity), 0) as storm_exposure,

        -- Wildfire exposure: max burn probability of overlapping fire zones
        COALESCE(MAX(w.wildfire_severity), 0) as wildfire_exposure

    FROM wherobots_open_data.overture.buildings_building b

    -- Left join flood zones (spatial intersection)
    LEFT JOIN silver_flood f
        ON ST_Intersects(b.geometry, f.geometry)

    -- Left join storms (within impact radius)
    LEFT JOIN silver_storms s
        ON ST_DWithin(
            ST_Transform(ST_Centroid(b.geometry), 'EPSG:4326', 'EPSG:3857'),
            ST_Transform(s.geometry, 'EPSG:4326', 'EPSG:3857'),
            s.impact_radius_m
        )

    -- Left join wildfire zones (spatial intersection)
    LEFT JOIN silver_wildfire w
        ON ST_Intersects(b.geometry, w.geometry)

    WHERE ST_Within(b.geometry, ST_GeomFromWKT('{AOI}'))

    GROUP BY b.id, b.geometry
""")

cursor.execute("""
    SELECT
        COUNT(*) as total,
        SUM(CASE WHEN flood_exposure > 0 THEN 1 ELSE 0 END) as flood_exposed,
        SUM(CASE WHEN storm_exposure > 0 THEN 1 ELSE 0 END) as storm_exposed,
        SUM(CASE WHEN wildfire_exposure > 0 THEN 1 ELSE 0 END) as fire_exposed
    FROM silver_buildings_hazards
""")
r = cursor.fetchone()
print(f"   Total buildings: {r[0]:,}")
print(f"   Flood-exposed:   {r[1]:,}")
print(f"   Storm-exposed:   {r[2]:,}")
print(f"   Fire-exposed:    {r[3]:,}")

print("\n" + "=" * 60)
print("  ✅ SILVER LAYER COMPLETE")
print("  Buildings joined with flood, storm, and wildfire exposure.")
print("  Next → 04_gold.py: Composite risk scoring")
print("=" * 60)
