"""
Extract OPERA DSWx-S1 flood raster for California (top flood date) from Wherobots,
mosaic into a single GeoTIFF, and upload to Felt.
"""

import base64
import os
import tempfile
import time

import numpy as np
import rasterio
from rasterio.merge import merge
import requests

from wherobots.db import connect
from wherobots.db.region import Region
from wherobots.db.runtime import Runtime
from dotenv import load_dotenv

load_dotenv()

# ── Config ──────────────────────────────────────────────────────────────────
WHEROBOTS_API_KEY = os.environ["WHEROBOTS_API_KEY"]
FELT_API_TOKEN = os.environ["FELT_API_TOKEN"]
FELT_BASE = "https://felt.com/api/v2"

CA_BBOX = "POLYGON((-124.48 32.53, -114.13 32.53, -114.13 42.01, -124.48 42.01, -124.48 32.53))"
TARGET_DATE = "2026-03-23"
OUTPUT_DIR = "data/flood_rasters"

# ── Step 1: Extract OPERA flood tiles from Wherobots ────────────────────────
QUERY = f"""
SELECT
    x, y,
    base64(RS_AsGeoTiff(raster)) AS raster_b64
FROM org_catalog.opera.dswx_s1
WHERE RS_Intersects(raster, ST_GeomFromText('{CA_BBOX}'))
  AND acq_date = DATE '{TARGET_DATE}'
  AND band = 'B01_WTR'
"""

print(f"[1/4] Extracting OPERA DSWx-S1 tiles for {TARGET_DATE}...")
with connect(
    api_key=WHEROBOTS_API_KEY,
    runtime=Runtime.TINY,
    region=Region.AWS_US_WEST_2,
) as conn:
    cur = conn.cursor()
    cur.execute(QUERY)
    df = cur.fetchall()

print(f"       Extracted {len(df)} tiles")

# ── Step 2: Decode tiles and mosaic ─────────────────────────────────────────
print("[2/4] Decoding and mosaicking...")
os.makedirs(OUTPUT_DIR, exist_ok=True)

tile_datasets = []
temp_files = []

for idx, row in df.iterrows():
    raster_bytes = base64.b64decode(row["raster_b64"])
    tmp = tempfile.NamedTemporaryFile(suffix=".tif", delete=False)
    tmp.write(raster_bytes)
    tmp.flush()
    temp_files.append(tmp.name)
    tile_datasets.append(rasterio.open(tmp.name))

mosaic, mosaic_transform = merge(tile_datasets)

output_path = os.path.join(OUTPUT_DIR, f"opera_flood_california_{TARGET_DATE}.tif")
with rasterio.open(
    output_path, "w", driver="GTiff",
    height=mosaic.shape[1], width=mosaic.shape[2],
    count=mosaic.shape[0], dtype=mosaic.dtype,
    crs=tile_datasets[0].crs or "EPSG:4326",
    transform=mosaic_transform,
) as dst:
    dst.write(mosaic)

for ds in tile_datasets:
    ds.close()
for f in temp_files:
    os.unlink(f)

file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
print(f"       Saved: {output_path} ({file_size_mb:.1f} MB)")

# ── Step 3: Create Felt map ─────────────────────────────────────────────────
print("[3/4] Creating Felt map...")
headers = {"Authorization": f"Bearer {FELT_API_TOKEN}", "Content-Type": "application/json"}

create_resp = requests.post(
    f"{FELT_BASE}/maps",
    headers=headers,
    json={"title": f"CA Flood — OPERA DSWx-S1 {TARGET_DATE} (AR3)", "lat": 37.5, "lon": -119.5, "zoom": 6},
)
create_resp.raise_for_status()
map_data = create_resp.json()
map_id = map_data["id"]
map_url = map_data["url"]
print(f"       Map: {map_url}")

# ── Step 4: Upload via presigned URL ────────────────────────────────────────
print("[4/4] Uploading to Felt...")
file_name = os.path.basename(output_path)
presign_resp = requests.post(
    f"{FELT_BASE}/maps/{map_id}/upload",
    headers=headers,
    json={"name": f"OPERA Flood {TARGET_DATE}", "file_names": [file_name]},
)
presign_resp.raise_for_status()
presign_data = presign_resp.json()

s3_url = presign_data["url"]
presigned_attrs = presign_data["presigned_attributes"]
layer_id = presign_data["layer_id"]

with open(output_path, "rb") as f:
    upload_resp = requests.post(
        s3_url,
        data={**presigned_attrs, "success_action_status": "204", "x-amz-meta-file-count": "1"},
        files={"file": (file_name, f)},
    )

if upload_resp.status_code not in (200, 201, 204):
    print(f"       S3 upload failed: {upload_resp.status_code}")
    exit(1)

print("       Waiting for processing...")
for _ in range(60):
    time.sleep(5)
    layers_resp = requests.get(
        f"{FELT_BASE}/maps/{map_id}/layers",
        headers={"Authorization": f"Bearer {FELT_API_TOKEN}"},
    )
    if layers_resp.ok:
        layers = layers_resp.json()
        data = layers if isinstance(layers, list) else layers.get("data", [])
        for layer in data:
            status = layer.get("status", "unknown")
            progress = layer.get("progress", 0)
            print(f"       {status} ({progress}%)")
            if status == "completed":
                print(f"\nDone! Map: {map_url}")
                exit(0)
            if status == "failed":
                print("       Layer processing failed!")
                exit(1)

print(f"\nMap: {map_url}")
