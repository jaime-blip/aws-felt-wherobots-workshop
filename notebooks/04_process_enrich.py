#!/usr/bin/env python3
"""
Step 4: Process & Enrich — Spatial Joins and Risk Scoring
==========================================================

This is where the magic happens. We'll:
1. Join buildings with flood zones (which buildings are flooded?)
2. Join buildings with severe weather events (proximity scoring)
3. Sample wildfire burn probability at building locations
4. Compute a composite risk score per building
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

# First, recreate the temp views from previous steps
# (In production, these would be persistent tables)
print("📋 Setting up datasets from Steps 2 & 3...")
# ... (execute the CREATE VIEW statements from steps 2-3)
# For brevity, we'll work with the Houston flood scenario

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. Spatial Join: Buildings × Flood Zones
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("🌊 Joining buildings with flood zones...")
cursor.execute("""
    CREATE OR REPLACE TEMP VIEW buildings_flood AS
    SELECT
        b.id as building_id,
        b.geometry as building_geom,
        b.names as building_name,
        f.flood_depth_m,
        f.observation_date,
        -- Flood risk score: 0-1 based on depth
        LEAST(f.flood_depth_m / 3.0, 1.0) as flood_risk_score
    FROM wherobots_open_data.overture.buildings_building b
    JOIN flood_zones f
        ON ST_Intersects(b.geometry, f.geometry)
    WHERE ST_Within(
        b.geometry,
        ST_GeomFromWKT('POLYGON((-95.55 29.60, -95.30 29.60, -95.30 29.85, -95.55 29.85, -95.55 29.60))')
    )
""")
cursor.execute("SELECT COUNT(*) FROM buildings_flood")
print(f"   → {cursor.fetchone()[0]:,} buildings in flood zones")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. Proximity Scoring: Buildings × Severe Weather Events
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n⛈️  Computing storm proximity scores...")
cursor.execute("""
    CREATE OR REPLACE TEMP VIEW buildings_storms AS
    SELECT
        b.building_id,
        b.building_geom,
        b.flood_risk_score,
        -- Count severe weather events within 5km
        COUNT(sw.id) as nearby_events,
        -- Storm risk: based on proximity and count
        LEAST(COUNT(sw.id) / 5.0, 1.0) as storm_risk_score
    FROM buildings_flood b
    LEFT JOIN severe_weather sw
        ON ST_Distance(
            ST_Transform(b.building_geom, 'EPSG:4326', 'EPSG:3857'),
            ST_Transform(sw.geometry, 'EPSG:4326', 'EPSG:3857')
        ) < 5000  -- 5km radius
    GROUP BY b.building_id, b.building_geom, b.flood_risk_score
""")
cursor.execute("SELECT AVG(nearby_events), AVG(storm_risk_score) FROM buildings_storms")
result = cursor.fetchone()
print(f"   Avg nearby events: {result[0]:.1f}, avg storm risk: {result[1]:.2f}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. Composite Risk Score
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

print("\n🎯 Computing composite risk scores...")
print("   Formula: 40% flood + 30% storm + 30% wildfire")

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW risk_scored_buildings AS
    SELECT
        building_id,
        building_geom,
        flood_risk_score,
        storm_risk_score,
        -- Composite score (wildfire = 0 for Houston, would be populated for LA)
        ROUND(
            (0.40 * flood_risk_score) +
            (0.30 * storm_risk_score) +
            (0.30 * 0.0),  -- wildfire placeholder
            3
        ) as composite_risk_score,
        CASE
            WHEN (0.40 * flood_risk_score + 0.30 * storm_risk_score) >= 0.7 THEN 'critical'
            WHEN (0.40 * flood_risk_score + 0.30 * storm_risk_score) >= 0.4 THEN 'high'
            WHEN (0.40 * flood_risk_score + 0.30 * storm_risk_score) >= 0.2 THEN 'moderate'
            ELSE 'low'
        END as risk_category
    FROM buildings_storms
""")

cursor.execute("""
    SELECT risk_category, COUNT(*), AVG(composite_risk_score)
    FROM risk_scored_buildings
    GROUP BY risk_category
    ORDER BY AVG(composite_risk_score) DESC
""")
print("   Risk distribution:")
for row in cursor.fetchall():
    print(f"     • {row[0]}: {row[1]:,} buildings (avg score: {row[2]:.2f})")

print("\n✅ Step 4 complete! Buildings scored with composite risk.")
print("   Next: 05_export_results.py — Export for the agent")
