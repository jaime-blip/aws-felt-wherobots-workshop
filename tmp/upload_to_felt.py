"""Upload existing flood GeoTIFF to Felt using the presigned URL flow."""
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

FELT_API_TOKEN = os.environ["FELT_API_TOKEN"]
FELT_BASE = "https://felt.com/api/v2"
OUTPUT_PATH = "data/flood_rasters/flood_california_2026-03-08.tif"
TARGET_DATE = "2026-03-08"

headers = {"Authorization": f"Bearer {FELT_API_TOKEN}"}

# 1. Create map
print("Creating map...")
create_resp = requests.post(
    f"{FELT_BASE}/maps",
    headers={**headers, "Content-Type": "application/json"},
    json={"title": f"CA Flood — MODIS NRT {TARGET_DATE}", "lat": 37.5, "lon": -119.5, "zoom": 6},
)
create_resp.raise_for_status()
map_data = create_resp.json()
map_id = map_data["id"]
map_url = map_data["url"]
print(f"Map: {map_url}")

# 2. Request presigned upload URL
print("Requesting upload URL...")
file_name = os.path.basename(OUTPUT_PATH)
presign_resp = requests.post(
    f"{FELT_BASE}/maps/{map_id}/upload",
    headers={**headers, "Content-Type": "application/json"},
    json={"name": f"MODIS Flood {TARGET_DATE}", "file_names": [file_name]},
)
presign_resp.raise_for_status()
presign_data = presign_resp.json()

# Felt returns: url, presigned_attributes, layer_id, layer_group_id
s3_url = presign_data["url"]
presigned_attrs = presign_data["presigned_attributes"]
layer_id = presign_data["layer_id"]
layer_group_id = presign_data["layer_group_id"]
print(f"Layer ID: {layer_id}")

# 3. Upload to S3 via multipart form POST
print("Uploading to S3...")
with open(OUTPUT_PATH, "rb") as f:
    files = {"file": (file_name, f)}
    form_data = {
        **presigned_attrs,
        "success_action_status": "204",
        "x-amz-meta-file-count": "1",
    }
    upload_resp = requests.post(s3_url, data=form_data, files=files)

print(f"S3 upload status: {upload_resp.status_code}")
if upload_resp.status_code not in (200, 201, 204):
    print(f"S3 error: {upload_resp.text[:500]}")
    exit(1)

# 4. Finish upload
print("Finishing upload...")
finish_resp = requests.post(
    f"{FELT_BASE}/maps/{map_id}/layers/{layer_id}/finish_upload",
    headers={**headers, "Content-Type": "application/json"},
    json={"filename": file_name, "name": f"MODIS Flood {TARGET_DATE}"},
)
print(f"Finish status: {finish_resp.status_code}")
# Don't fail on this — some API versions don't need it

# 5. Poll for processing
print("Waiting for processing...")
for i in range(60):
    time.sleep(5)
    layers_resp = requests.get(f"{FELT_BASE}/maps/{map_id}/layers", headers=headers)
    if layers_resp.ok:
        layers = layers_resp.json()
        data = layers.get("data", layers) if isinstance(layers, dict) else layers
        if isinstance(data, list):
            for layer in data:
                status = layer.get("status", "unknown")
                progress = layer.get("progress", 0)
                name = layer.get("name", "?")
                print(f"  {name}: {status} ({progress}%)")
                if status == "completed":
                    print(f"\nDone! Map: {map_url}")
                    exit(0)
                if status == "failed":
                    print("Layer failed!")
                    exit(1)

print(f"\nMap: {map_url}")
