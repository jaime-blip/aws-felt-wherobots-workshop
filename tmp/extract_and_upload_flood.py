"""
Extract MODIS flood raster tiles for California (March 8, 2026) from Wherobots,
mosaic into a single GeoTIFF, and upload to Felt.
"""

import base64
import os
import tempfile
import time

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.transform import from_bounds
import requests

from wherobots.db import connect
from wherobots.db.region import Region
from wherobots.db.runtime import Runtime

# ── Load .env ───────────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
WHEROBOTS_API_KEY = "f3a4ca09-283b-4427-9ad9-ebb81086ad69"
FELT_API_TOKEN = os.environ.get("FELT_API_TOKEN", "")

CA_BBOX = "POLYGON((-124.48 32.53, -114.13 32.53, -114.13 42.01, -124.48 42.01, -124.48 32.53))"
TARGET_DATE = "2026-03-08"
OUTPUT_DIR = "data/flood_rasters"

# ── Step 1: Extract flood tiles from Wherobots ──────────────────────────────
QUERY = f"""
SELECT
    x, y,
    base64(RS_AsGeoTiff(RS_SetSRID(raster, 4326))) AS raster_b64
FROM org_catalog.modis.MCDWD_L3_F3_NRT
WHERE RS_Intersects(raster, ST_GeomFromText('{CA_BBOX}'))
  AND acq_date = DATE '{TARGET_DATE}'
"""

print(f"[1/4] Connecting to Wherobots and extracting tiles for {TARGET_DATE}...")
with connect(
    api_key=WHEROBOTS_API_KEY,
    runtime=Runtime.TINY,
    region=Region.AWS_US_WEST_2,
) as conn:
    cur = conn.cursor()
    cur.execute(QUERY)
    df = cur.fetchall()

print(f"       Extracted {len(df)} tiles")

# ── Step 2: Decode tiles and write to temp files ────────────────────────────
print("[2/4] Decoding tiles and mosaicking...")
os.makedirs(OUTPUT_DIR, exist_ok=True)

tile_datasets = []
temp_files = []

for idx, row in df.iterrows():
    raster_bytes = base64.b64decode(row["raster_b64"])
    tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    tmp.write(raster_bytes)
    tmp.flush()
    temp_files.append(tmp.name)

    ds = rasterio.open(tmp.name)
    tile_datasets.append(ds)

# ── Step 3: Mosaic into single GeoTIFF ──────────────────────────────────────
print("[3/4] Merging into single GeoTIFF...")
mosaic, mosaic_transform = merge(tile_datasets)

output_path = os.path.join(OUTPUT_DIR, f"flood_california_{TARGET_DATE}.tif")
with rasterio.open(
    output_path,
    "w",
    driver="GTiff",
    height=mosaic.shape[1],
    width=mosaic.shape[2],
    count=mosaic.shape[0],
    dtype=mosaic.dtype,
    crs="EPSG:4326",
    transform=mosaic_transform,
) as dst:
    dst.write(mosaic)

# Cleanup
for ds in tile_datasets:
    ds.close()
for f in temp_files:
    os.unlink(f)

file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
print(f"       Saved: {output_path} ({file_size_mb:.1f} MB)")

# ── Step 4: Create Felt map and upload ───────────────────────────────────────
print("[4/4] Uploading to Felt...")

if not FELT_API_TOKEN:
    raise RuntimeError("FELT_API_TOKEN not set — add it to .env")

FELT_BASE = "https://felt.com/api/v2"
headers = {
    "Authorization": f"Bearer {FELT_API_TOKEN}",
    "Content-Type": "application/json",
}

# Create map
create_resp = requests.post(
    f"{FELT_BASE}/maps",
    headers=headers,
    json={"title": f"CA Flood — MODIS NRT {TARGET_DATE}", "lat": 37.5, "lon": -119.5, "zoom": 6},
)
create_resp.raise_for_status()
map_data = create_resp.json()
map_id = map_data["id"]
map_url = map_data["url"]
print(f"       Created map: {map_url}")

# Upload file via multipart
upload_headers = {"Authorization": f"Bearer {FELT_API_TOKEN}"}
with open(output_path, "rb") as f:
    upload_resp = requests.post(
        f"{FELT_BASE}/maps/{map_id}/upload",
        headers=upload_headers,
        files={"file": (os.path.basename(output_path), f, "image/tiff")},
        data={"layer_name": f"MODIS Flood {TARGET_DATE}"},
    )
upload_resp.raise_for_status()
upload_data = upload_resp.json()
print(f"       Uploaded! Layer: {upload_data.get('layer_id', 'processing')}")

# Poll for processing
layer_id = upload_data.get("layer_id")
if layer_id:
    for _ in range(30):
        time.sleep(3)
        layer_resp = requests.get(f"{FELT_BASE}/maps/{map_id}/layers/{layer_id}", headers=headers)
        if layer_resp.ok:
            status = layer_resp.json().get("status", "unknown")
            print(f"       Processing: {status}")
            if status == "completed":
                break
            if status == "failed":
                print("       WARNING: Layer processing failed")
                break

print(f"\n       Map URL: {map_url}")

print("\nDone!")
