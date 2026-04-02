"""Query MODIS flood extent for California — find dates with highest flood activity."""

from wherobots.db import connect
from wherobots.db.region import Region
from wherobots.db.runtime import Runtime

API_KEY = "f3a4ca09-283b-4427-9ad9-ebb81086ad69"

# California bounding box (EPSG:4326)
CA_BBOX = "POLYGON((-124.48 32.53, -114.13 32.53, -114.13 42.01, -124.48 42.01, -124.48 32.53))"

# Query 1: Check full date range available in the table (no CA filter for speed)
QUERY_DATES = """
SELECT
    MIN(acq_date) AS earliest_date,
    MAX(acq_date) AS latest_date,
    COUNT(DISTINCT acq_date) AS total_dates
FROM org_catalog.modis.MCDWD_L3_F3_NRT
"""

# Query 2: Get all distinct dates, grouped by month
QUERY_ALL_DATES = """
SELECT
    acq_date,
    COUNT(*) AS tile_count
FROM org_catalog.modis.MCDWD_L3_F3_NRT
GROUP BY acq_date
ORDER BY acq_date
"""

print("Connecting to Wherobots...")
with connect(
    api_key=API_KEY,
    runtime=Runtime.TINY,
    region=Region.AWS_US_WEST_2,
) as conn:
    cur = conn.cursor()

    print("Query 1: Date range in MODIS table...")
    cur.execute(QUERY_DATES)
    print(cur.fetchall().to_string(index=False))

    print("\nQuery 2: All dates with tile counts...")
    cur.execute(QUERY_ALL_DATES)
    df = cur.fetchall()
    print(df.to_string(index=False))
    print(f"\nTotal distinct dates: {len(df)}")
