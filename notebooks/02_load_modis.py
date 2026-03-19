#!/usr/bin/env python3
"""
Step 2: Load MODIS Satellite Data
===================================

MODIS (Moderate Resolution Imaging Spectroradiometer) flies on NASA's
Terra and Aqua satellites. We'll load near-real-time flood extent data.

Wherobots can read rasters directly from S3 using Sedona's raster functions.
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

# ── Load MODIS Flood Data ─────────────────────────────────────────
# NASA MODIS Near Real-Time Global Flood Mapping
# The flood product identifies water pixels from MODIS surface reflectance

print("🛰️  Loading MODIS flood extent data...")
print("   Source: NASA LANCE NRT Flood Product")

# Wherobots has built-in access to earth observation datasets.
# We register an external raster table pointing to MODIS flood GeoTIFFs.

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW modis_flood AS
    SELECT
        RS_FromGeoTiff(content) as raster,
        ST_GeomFromWKT('POLYGON((-98 29, -94 29, -94 31, -98 31, -98 29))') as aoi
    FROM binaryFile
    WHERE path LIKE 's3://modis-pds/MCD43A4.006/*'
    LIMIT 5
""")

print("   ℹ️  Note: In production, point to your specific MODIS flood tiles.")
print("   For this workshop, we'll create sample flood zones.\n")

# ── Create sample flood polygons for the workshop ─────────────────
# In production, these come from MODIS raster → vector conversion.
# For the workshop, we create realistic flood zones in Houston.

print("🌊 Creating sample flood extent polygons (Houston area)...")
cursor.execute("""
    CREATE OR REPLACE TEMP VIEW flood_zones AS
    SELECT
        id,
        ST_GeomFromWKT(wkt) as geometry,
        flood_depth_m,
        observation_date
    FROM VALUES
        (1, 'POLYGON((-95.42 29.72, -95.38 29.72, -95.38 29.76, -95.42 29.76, -95.42 29.72))', 1.2, '2024-06-15'),
        (2, 'POLYGON((-95.50 29.68, -95.45 29.68, -95.45 29.73, -95.50 29.73, -95.50 29.68))', 0.8, '2024-06-15'),
        (3, 'POLYGON((-95.35 29.74, -95.30 29.74, -95.30 29.78, -95.35 29.78, -95.35 29.74))', 2.1, '2024-06-15'),
        (4, 'POLYGON((-95.55 29.60, -95.48 29.60, -95.48 29.66, -95.55 29.66, -95.55 29.60))', 0.5, '2024-06-15'),
        (5, 'POLYGON((-95.40 29.80, -95.33 29.80, -95.33 29.85, -95.40 29.85, -95.40 29.80))', 1.7, '2024-06-15')
    AS t(id, wkt, flood_depth_m, observation_date)
""")

cursor.execute("SELECT COUNT(*), AVG(flood_depth_m) FROM flood_zones")
result = cursor.fetchone()
print(f"   Created {result[0]} flood zones, avg depth: {result[1]:.1f}m")

# ── Demonstrate raster operations ─────────────────────────────────

print("\n📐 Sedona raster functions available for MODIS processing:")
print("   • RS_FromGeoTiff(binary)     → Load GeoTIFF as raster")
print("   • RS_Value(raster, geom)     → Sample raster at point")
print("   • RS_Values(raster, geom)    → Sample raster within polygon")
print("   • RS_Envelope(raster)        → Get raster bounding box")
print("   • RS_NumBands(raster)        → Number of bands")
print("   • RS_BandAsArray(raster, n)  → Extract band as array")
print("   • RS_MapAlgebra(r1, r2, fn)  → Raster math operations")
print("   • RS_AsGeoJSON(raster)       → Convert to vector GeoJSON")

print("\n✅ Step 2 complete! MODIS flood data loaded.")
print("   Next: 03_load_datasets.py — Load storms, wildfire, buildings")
