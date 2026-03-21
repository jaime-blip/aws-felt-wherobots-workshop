#!/usr/bin/env python3
"""
Step 4: Gold Layer — Composite Risk Scoring
=============================================

GOLD = business-ready, aggregated, scored data.

We compute a composite climate risk score per building:
  composite = (0.40 × flood) + (0.30 × storm) + (0.30 × wildfire)

Then classify into risk categories: critical / high / moderate / low.
This is the table that goes into Aurora PostgreSQL for the agent.
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
print("  GOLD LAYER — Composite Risk Scoring")
print("=" * 60)

# NOTE: Requires silver views from 03_silver.py
# In production, silver tables are persistent.

# ── Compute composite risk scores ────────────────────────────────

print("\n🎯 Computing composite risk scores...")
print("   Formula: 0.40×flood + 0.30×storm + 0.30×wildfire")

cursor.execute("""
    CREATE OR REPLACE TEMP VIEW gold_building_risk AS
    SELECT
        building_id,
        lon,
        lat,
        building_geom,

        -- Individual hazard scores (0-1)
        ROUND(flood_exposure, 3) as flood_risk,
        ROUND(storm_exposure, 3) as storm_risk,
        ROUND(wildfire_exposure, 3) as wildfire_risk,

        -- Composite score
        ROUND(
            (0.40 * flood_exposure) +
            (0.30 * storm_exposure) +
            (0.30 * wildfire_exposure),
            3
        ) as composite_risk,

        -- Risk category
        CASE
            WHEN (0.40 * flood_exposure + 0.30 * storm_exposure + 0.30 * wildfire_exposure) >= 0.6 THEN 'critical'
            WHEN (0.40 * flood_exposure + 0.30 * storm_exposure + 0.30 * wildfire_exposure) >= 0.35 THEN 'high'
            WHEN (0.40 * flood_exposure + 0.30 * storm_exposure + 0.30 * wildfire_exposure) >= 0.15 THEN 'moderate'
            ELSE 'low'
        END as risk_category,

        -- Dominant hazard
        CASE
            WHEN flood_exposure >= storm_exposure AND flood_exposure >= wildfire_exposure THEN 'flood'
            WHEN storm_exposure >= flood_exposure AND storm_exposure >= wildfire_exposure THEN 'storm'
            ELSE 'wildfire'
        END as dominant_hazard,

        CURRENT_TIMESTAMP() as scored_at

    FROM silver_buildings_hazards
""")

# ── Summary statistics ────────────────────────────────────────────

print("\n📊 Risk distribution:")
cursor.execute("""
    SELECT
        risk_category,
        COUNT(*) as buildings,
        ROUND(AVG(composite_risk), 3) as avg_score,
        ROUND(MAX(composite_risk), 3) as max_score
    FROM gold_building_risk
    GROUP BY risk_category
    ORDER BY avg_score DESC
""")
for row in cursor.fetchall():
    emoji = {"critical": "🔴", "high": "🟠", "moderate": "🟡", "low": "🟢"}.get(row[0], "⚪")
    print(f"   {emoji} {row[0]:10s}: {row[1]:,} buildings | avg: {row[2]} | max: {row[3]}")

print("\n📊 Dominant hazard breakdown:")
cursor.execute("""
    SELECT dominant_hazard, COUNT(*), ROUND(AVG(composite_risk), 3)
    FROM gold_building_risk
    GROUP BY dominant_hazard
    ORDER BY COUNT(*) DESC
""")
for row in cursor.fetchall():
    print(f"   • {row[0]}: {row[1]:,} buildings (avg risk: {row[2]})")

print("\n📊 Top 10 highest-risk buildings:")
cursor.execute("""
    SELECT building_id, ROUND(composite_risk, 3), risk_category, dominant_hazard,
           ROUND(flood_risk, 2), ROUND(storm_risk, 2), ROUND(wildfire_risk, 2)
    FROM gold_building_risk
    ORDER BY composite_risk DESC
    LIMIT 10
""")
for row in cursor.fetchall():
    print(f"   {row[0]}: score={row[1]} ({row[2]}) | dominant={row[3]} | F:{row[4]} S:{row[5]} W:{row[6]}")

print("\n" + "=" * 60)
print("  ✅ GOLD LAYER COMPLETE")
print("  Every building has a composite risk score + category.")
print("  Next → 05_export_aurora.py: JDBC export to Aurora PostgreSQL")
print("=" * 60)
