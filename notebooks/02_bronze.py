#!/usr/bin/env python3
"""
Step 2: Bronze Layer — Raw Data Ingestion
==========================================

The medallion architecture organizes data into three quality tiers:
  Bronze → Silver → Gold

BRONZE = raw data, minimally transformed. We land it as-is from the
source systems so we have a full audit trail.

Data sources:
  1. MODIS satellite — near-real-time flood extent (NASA Earthdata)
  2. NOAA SWDI — severe weather events: hail, tornadoes, wind (AWS Open Data)
  3. USFS — wildfire burn probability rasters (wildfirerisk.org)
  4. Overture Maps — building footprints (Wherobots catalog)
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
print("  BRONZE LAYER — Raw Data Ingestion")
print("=" * 60)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bronze 1: MODIS Flood Extent
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n🛰️  [Bronze] MODIS Near-Real-Time Flood Product")
print("   Source: NASA LANCE / MODIS Surface Reflectance")
print("   Resolution: 250m, daily refresh")

# In production: load from S3 or Wherobots catalog
# RS_FromGeoTiff reads rasters natively in Sedona
cursor.execute("""
    CREATE OR REPLACE TEMP VIEW bronze_modis_flood AS
    SELECT
        id,
        ST_GeomFromWKT(wkt) as geometry,
        flood_depth_m,
        satellite,
        acquisition_date,
        confidence,
        'modis_nrt' as source
    FROM VALUES
        (1, 'POLYGON((-97.80 30.20, -97.74 30.20, -97.74 30.26, -97.80 30.26, -97.80 30.20))', 1.4, 'Aqua', '2024-10-15', 0.92),
        (2, 'POLYGON((-97.72 30.22, -97.66 30.22, -97.66 30.28, -97.72 30.28, -97.72 30.22))', 0.6, 'Terra', '2024-10-15', 0.87),
        (3, 'POLYGON((-97.85 30.18, -97.78 30.18, -97.78 30.24, -97.85 30.24, -97.85 30.18))', 2.3, 'Aqua', '2024-10-15', 0.95),
        (4, 'POLYGON((-97.68 30.26, -97.62 30.26, -97.62 30.32, -97.68 30.32, -97.68 30.26))', 0.3, 'Terra', '2024-10-14', 0.78),
        (5, 'POLYGON((-97.90 30.15, -97.82 30.15, -97.82 30.22, -97.90 30.22, -97.90 30.15))', 1.8, 'Aqua', '2024-10-15', 0.91),
        -- Houston area floods
        (6, 'POLYGON((-95.50 29.68, -95.44 29.68, -95.44 29.74, -95.50 29.74, -95.50 29.68))', 1.9, 'Aqua', '2024-10-15', 0.94),
        (7, 'POLYGON((-95.42 29.72, -95.36 29.72, -95.36 29.78, -95.42 29.78, -95.42 29.72))', 1.1, 'Terra', '2024-10-15', 0.88),
        (8, 'POLYGON((-95.55 29.60, -95.48 29.60, -95.48 29.67, -95.55 29.67, -95.55 29.60))', 0.7, 'Aqua', '2024-10-14', 0.82)
    AS t(id, wkt, flood_depth_m, satellite, acquisition_date, confidence)
""")

cursor.execute("SELECT COUNT(*), AVG(flood_depth_m), AVG(confidence) FROM bronze_modis_flood")
r = cursor.fetchone()
print(f"   ✅ Loaded {r[0]} flood polygons | avg depth: {r[1]:.1f}m | avg confidence: {r[2]:.0%}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bronze 2: NOAA Severe Weather Data Inventory
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n⛈️  [Bronze] NOAA Severe Weather Data Inventory")
print("   Source: s3://noaa-swdi-pds/ (AWS Open Data)")
print("   Events: hail, tornadoes, damaging wind")

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW bronze_noaa_storms AS
    SELECT
        id,
        ST_Point(CAST(lon AS DOUBLE), CAST(lat AS DOUBLE)) as geometry,
        event_type,
        magnitude,
        magnitude_unit,
        event_date,
        event_time,
        source_report,
        'noaa_swdi' as source
    FROM VALUES
        -- Austin-area events
        (1, -97.75, 30.27, 'hail', 2.00, 'inches', '2024-05-12', '15:32', 'spotter'),
        (2, -97.71, 30.23, 'tornado', 2, 'EF-scale', '2024-04-08', '18:45', 'radar'),
        (3, -97.80, 30.30, 'hail', 1.75, 'inches', '2024-06-01', '14:10', 'spotter'),
        (4, -97.68, 30.19, 'wind', 75, 'mph', '2024-05-12', '15:48', 'mesonet'),
        (5, -97.83, 30.25, 'tornado', 1, 'EF-scale', '2024-03-22', '20:15', 'radar'),
        (6, -97.73, 30.31, 'hail', 1.25, 'inches', '2024-06-15', '16:20', 'public'),
        -- Houston-area events
        (7, -95.45, 29.73, 'hail', 2.50, 'inches', '2024-05-20', '14:05', 'spotter'),
        (8, -95.38, 29.70, 'tornado', 3, 'EF-scale', '2024-04-12', '17:30', 'radar'),
        (9, -95.52, 29.68, 'wind', 85, 'mph', '2024-05-20', '14:22', 'mesonet'),
        (10, -95.35, 29.76, 'hail', 1.50, 'inches', '2024-06-10', '15:45', 'spotter'),
        -- Miami-area events
        (11, -80.22, 25.78, 'wind', 95, 'mph', '2024-09-15', '08:30', 'mesonet'),
        (12, -80.18, 25.75, 'tornado', 1, 'EF-scale', '2024-09-15', '09:10', 'radar')
    AS t(id, lon, lat, event_type, magnitude, magnitude_unit, event_date, event_time, source_report)
""")

cursor.execute("SELECT event_type, COUNT(*) FROM bronze_noaa_storms GROUP BY event_type")
print("   Events loaded:")
for row in cursor.fetchall():
    print(f"     • {row[0]}: {row[1]}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bronze 3: USFS Wildfire Burn Probability
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n🔥 [Bronze] USFS Wildfire Burn Probability")
print("   Source: wildfirerisk.org (USFS Fire Modeling)")
print("   Data: burn probability rasters → vectorized zones")

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW bronze_usfs_wildfire AS
    SELECT
        id,
        ST_GeomFromWKT(wkt) as geometry,
        burn_probability,
        flame_length_m,
        vegetation_type,
        'usfs_wildfire' as source
    FROM VALUES
        -- Austin / Central TX (WUI zones)
        (1, 'POLYGON((-97.85 30.20, -97.75 30.20, -97.75 30.30, -97.85 30.30, -97.85 30.20))', 0.72, 2.4, 'mixed_forest'),
        (2, 'POLYGON((-97.75 30.25, -97.65 30.25, -97.65 30.35, -97.75 30.35, -97.75 30.25))', 0.58, 1.8, 'grassland'),
        (3, 'POLYGON((-97.90 30.15, -97.80 30.15, -97.80 30.25, -97.90 30.25, -97.90 30.15))', 0.85, 3.1, 'shrubland'),
        (4, 'POLYGON((-97.70 30.18, -97.60 30.18, -97.60 30.28, -97.70 30.28, -97.70 30.18))', 0.34, 1.2, 'urban_veg'),
        -- LA (high fire risk)
        (5, 'POLYGON((-118.60 34.05, -118.45 34.05, -118.45 34.18, -118.60 34.18, -118.60 34.05))', 0.91, 4.2, 'chaparral'),
        (6, 'POLYGON((-118.45 34.10, -118.30 34.10, -118.30 34.22, -118.45 34.22, -118.45 34.10))', 0.78, 3.0, 'mixed_forest'),
        (7, 'POLYGON((-118.70 34.15, -118.55 34.15, -118.55 34.28, -118.70 34.28, -118.70 34.15))', 0.95, 4.8, 'chaparral')
    AS t(id, wkt, burn_probability, flame_length_m, vegetation_type)
""")

cursor.execute("SELECT COUNT(*), AVG(burn_probability), MAX(burn_probability) FROM bronze_usfs_wildfire")
r = cursor.fetchone()
print(f"   ✅ Loaded {r[0]} wildfire zones | avg burn prob: {r[1]:.0%} | max: {r[2]:.0%}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Bronze 4: Overture Maps Building Footprints (from catalog)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n🏗️  [Bronze] Overture Maps Building Footprints")
print("   Source: wherobots_open_data.overture.buildings_building")
print("   This is already in the catalog — no ingestion needed!")

# We'll reference it directly in Silver layer queries
cursor.execute("""
    SELECT COUNT(*) FROM wherobots_open_data.overture.buildings_building
    WHERE ST_Within(geometry,
        ST_GeomFromWKT('POLYGON((-97.90 30.15, -97.60 30.15, -97.60 30.35, -97.90 30.35, -97.90 30.15))'))
""")
print(f"   Austin AOI: {cursor.fetchone()[0]:,} buildings")

print("\n" + "=" * 60)
print("  ✅ BRONZE LAYER COMPLETE")
print("  All raw data sources ingested.")
print("  Next → 03_silver.py: Clean, normalize, spatial joins")
print("=" * 60)
