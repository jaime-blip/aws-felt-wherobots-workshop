#!/usr/bin/env python3
"""
Step 1: Setup & Connect to Wherobots Cloud
============================================

Wherobots Cloud runs Apache Sedona — a distributed spatial engine that
processes terabytes of geospatial data with SQL. Think Spark + PostGIS.

In this workshop, we use Wherobots as our data engineering layer to
ingest, clean, and score satellite + weather data (medallion architecture).
The results get exported to Aurora PostgreSQL for the agent to query.
"""

import os
from dotenv import load_dotenv

load_dotenv()

from wherobots.db import connect, Region, Runtime

print("🚀 Connecting to Wherobots Cloud...")
print("   Runtime: TINY (workshop mode — scale up for production)")
print("   This spins up a Sedona cluster — may take 1-2 minutes on cold start.\n")

conn = connect(
    host="api.cloud.wherobots.com",
    api_key=os.environ["WHEROBOTS_API_KEY"],
    runtime=Runtime.TINY,
    region=Region.AWS_US_WEST_2,
)
cursor = conn.cursor()
print("✅ Connected!\n")

# ── Explore the Wherobots data catalog ────────────────────────────

print("📚 Available schemas in wherobots_open_data:")
cursor.execute("SHOW SCHEMAS IN wherobots_open_data")
for row in cursor.fetchall():
    print(f"   • {row[0]}")

print("\n📚 Tables in the overture schema:")
cursor.execute("SHOW TABLES IN wherobots_open_data.overture")
for row in cursor.fetchall():
    print(f"   • {row[0]}")

# ── Quick sanity check ────────────────────────────────────────────

print("\n🏗️  Quick check: buildings in downtown Austin...")
cursor.execute("""
    SELECT COUNT(*) as building_count
    FROM wherobots_open_data.overture.buildings_building
    WHERE ST_Within(
        geometry,
        ST_GeomFromWKT('POLYGON((-97.76 30.25, -97.72 30.25, -97.72 30.28, -97.76 30.28, -97.76 30.25))')
    )
""")
print(f"   Found {cursor.fetchone()[0]:,} buildings in downtown Austin\n")

print("✅ Step 1 complete! Wherobots is ready.")
print("   Next → 02_bronze.py: Ingest raw data sources")
