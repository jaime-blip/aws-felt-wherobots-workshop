#!/usr/bin/env python3
"""
Step 3: Load Additional Datasets
==================================

We'll load three more datasets to build a comprehensive risk picture:
1. NOAA Severe Weather Data Inventory (hail & tornado events)
2. USFS Wildfire burn probability
3. Overture Maps building footprints (from Wherobots catalog)
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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataset 1: NOAA Severe Weather (Hail & Tornado Events)
# Source: s3://noaa-swdi-pds/
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("⛈️  Loading NOAA Severe Weather Data Inventory...")
print("   Source: s3://noaa-swdi-pds/ (AWS Open Data)")

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW severe_weather AS
    SELECT
        id,
        ST_Point(CAST(lon AS DOUBLE), CAST(lat AS DOUBLE)) as geometry,
        event_type,
        severity,
        event_date,
        description
    FROM VALUES
        (1, -95.37, 29.76, 'hail', 'severe', '2024-05-20', '2 inch hail reported'),
        (2, -95.41, 29.71, 'tornado', 'significant', '2024-04-12', 'EF2 tornado'),
        (3, -95.33, 29.80, 'hail', 'moderate', '2024-06-01', '1 inch hail'),
        (4, -95.48, 29.65, 'tornado', 'weak', '2024-03-28', 'EF0 brief touchdown'),
        (5, -95.52, 29.69, 'hail', 'severe', '2024-05-20', '1.75 inch hail'),
        (6, -95.36, 29.73, 'wind', 'significant', '2024-06-10', '75 mph wind gust'),
        (7, -95.44, 29.78, 'hail', 'moderate', '2024-04-15', '1.25 inch hail'),
        (8, -95.39, 29.82, 'tornado', 'weak', '2024-05-05', 'EF1 tornado')
    AS t(id, lon, lat, event_type, severity, event_date, description)
""")

cursor.execute("SELECT event_type, COUNT(*) FROM severe_weather GROUP BY event_type")
print("   Events loaded:")
for row in cursor.fetchall():
    print(f"     • {row[0]}: {row[1]} events")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataset 2: USFS Wildfire Burn Probability
# Source: wildfirerisk.org (USFS/MTBS)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n🔥 Loading USFS Wildfire burn probability...")
print("   Source: wildfirerisk.org (USFS Fire Modeling)")

# In production: load GeoTIFF raster of burn probabilities
# For workshop: create sample burn probability zones

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW wildfire_risk AS
    SELECT
        id,
        ST_GeomFromWKT(wkt) as geometry,
        burn_probability,
        risk_class
    FROM VALUES
        (1, 'POLYGON((-118.60 34.00, -118.40 34.00, -118.40 34.15, -118.60 34.15, -118.60 34.00))', 0.82, 'extreme'),
        (2, 'POLYGON((-118.40 34.05, -118.25 34.05, -118.25 34.18, -118.40 34.18, -118.40 34.05))', 0.65, 'high'),
        (3, 'POLYGON((-118.70 34.10, -118.55 34.10, -118.55 34.25, -118.70 34.25, -118.70 34.10))', 0.91, 'extreme'),
        (4, 'POLYGON((-118.30 34.12, -118.15 34.12, -118.15 34.22, -118.30 34.22, -118.30 34.12))', 0.45, 'moderate'),
        (5, 'POLYGON((-118.50 33.95, -118.35 33.95, -118.35 34.05, -118.50 34.05, -118.50 33.95))', 0.28, 'low')
    AS t(id, wkt, burn_probability, risk_class)
""")

cursor.execute("SELECT risk_class, COUNT(*), AVG(burn_probability) FROM wildfire_risk GROUP BY risk_class ORDER BY AVG(burn_probability) DESC")
print("   Wildfire risk zones:")
for row in cursor.fetchall():
    print(f"     • {row[0]}: {row[1]} zones, avg burn prob: {row[2]:.0%}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Dataset 3: Overture Maps Building Footprints
# Source: Wherobots built-in catalog
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n🏗️  Loading Overture Maps building footprints...")
print("   Source: wherobots_open_data.overture.buildings_building")

# Query buildings in our area of interest (Houston for flood, LA for fire)
cursor.execute("""
    SELECT COUNT(*) as cnt
    FROM wherobots_open_data.overture.buildings_building
    WHERE ST_Within(
        geometry,
        ST_GeomFromWKT('POLYGON((-95.55 29.60, -95.30 29.60, -95.30 29.85, -95.55 29.85, -95.55 29.60))')
    )
""")
houston_count = cursor.fetchone()[0]
print(f"   Houston AOI: {houston_count:,} buildings")

cursor.execute("""
    SELECT COUNT(*) as cnt
    FROM wherobots_open_data.overture.buildings_building
    WHERE ST_Within(
        geometry,
        ST_GeomFromWKT('POLYGON((-118.70 33.95, -118.15 33.95, -118.15 34.25, -118.70 34.25, -118.70 33.95))')
    )
""")
la_count = cursor.fetchone()[0]
print(f"   LA County AOI: {la_count:,} buildings")

print("\n✅ Step 3 complete! All datasets loaded.")
print("   Next: 04_process_enrich.py — Spatial joins & risk scoring")
