#!/usr/bin/env python3
"""
Step 1: Connect to Wherobots Cloud
===================================

Wherobots Cloud runs Apache Sedona — a distributed spatial engine
that can process terabytes of geospatial data with SQL.

We'll connect and explore the built-in data catalog.
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# ── Connect to Wherobots ──────────────────────────────────────────

from wherobots.db import connect, Region, Runtime

WHEROBOTS_API_KEY = os.environ["WHEROBOTS_API_KEY"]

print("🚀 Connecting to Wherobots Cloud...")
print("   (This spins up a Sedona cluster — may take 1-2 minutes on first run)")

conn = connect(
    host="api.cloud.wherobots.com",
    api_key=WHEROBOTS_API_KEY,
    runtime=Runtime.TINY,       # TINY for workshop, scale up for production
    region=Region.AWS_US_WEST_2,
)
cursor = conn.cursor()
print("✅ Connected!\n")

# ── Explore the catalog ───────────────────────────────────────────

print("📚 Available schemas in wherobots_open_data:")
cursor.execute("SHOW SCHEMAS IN wherobots_open_data")
schemas = cursor.fetchall()
for row in schemas:
    print(f"   • {row[0]}")

print("\n📚 Tables in the overture schema:")
cursor.execute("SHOW TABLES IN wherobots_open_data.overture")
tables = cursor.fetchall()
for row in tables:
    print(f"   • {row[0]}")

# ── Quick test: count buildings in a bounding box ─────────────────

print("\n🏗️  Quick test: counting buildings in downtown LA...")
cursor.execute("""
    SELECT COUNT(*) as building_count
    FROM wherobots_open_data.overture.buildings_building
    WHERE ST_Within(
        geometry,
        ST_GeomFromWKT('POLYGON((-118.28 34.03, -118.23 34.03, -118.23 34.06, -118.28 34.06, -118.28 34.03))')
    )
""")
result = cursor.fetchone()
print(f"   Found {result[0]:,} buildings in DTLA bounding box")

print("\n✅ Step 1 complete! Wherobots is ready for spatial queries.")
print("   Next: 02_load_modis.py — Load MODIS satellite data")
