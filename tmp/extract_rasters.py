#!/usr/bin/env python3
"""Extract burn probability rasters from Wherobots MCP, mosaic, and upload to Felt."""

import base64
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
import requests

WB_MCP_URL = "https://api.cloud.wherobots.com/mcp"
WB_API_KEY = os.environ.get("WHEROBOTS_API_KEY", "19e484ca-8088-4b22-b920-f0600a64dc26")

SD_BBOX_5070 = "POLYGON((-1920000 1530000, -1840000 1530000, -1840000 1620000, -1920000 1620000, -1920000 1530000))"

OUTPUT_DIR = Path("data/burn_probability_rasters")
MERGED_OUTPUT = OUTPUT_DIR / "burn_probability_sandiego.tif"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "X-API-Key": WB_API_KEY,
}

BATCH_SIZE = 20  # bigger batches = fewer round trips


def mcp_call(method, params, session_id=None):
    headers = {**HEADERS}
    if session_id:
        headers["Mcp-Session-Id"] = session_id
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(WB_MCP_URL, json=payload, headers=headers, timeout=600)
    result = None
    session = resp.headers.get("mcp-session-id")
    for line in resp.text.split("\n"):
        if line.startswith("data: "):
            try:
                data = json.loads(line[6:])
                if "result" in data:
                    result = data["result"]
            except json.JSONDecodeError:
                pass
    return result, session


def init_session():
    result, session_id = mcp_call("initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "extract-rasters", "version": "1.0"},
    })
    print(f"Session: {session_id}", flush=True)
    return session_id


def execute_query(session_id, query, limit=10):
    result, _ = mcp_call("tools/call", {
        "name": "execute_query_tool",
        "arguments": {"query": query, "limit": limit},
    }, session_id)
    if result and "content" in result:
        for item in result["content"]:
            if item["type"] == "text":
                return json.loads(item["text"])
    return None


def get_existing_tiles():
    """Get set of already-downloaded tile coords."""
    existing = set()
    for f in OUTPUT_DIR.glob("bp_tile_*.tif"):
        parts = f.stem.split("_")
        if len(parts) == 4:
            existing.add((int(parts[2]), int(parts[3])))
    return existing


def extract_tiles(session_id):
    """Extract all San Diego burn probability tiles, skipping already downloaded."""
    existing = get_existing_tiles()
    print(f"Already have {len(existing)} tiles on disk", flush=True)

    # Get all tile coordinates
    coord_result = execute_query(session_id, f"""
        SELECT x, y FROM org_catalog.wildfire_risk.burn_probability_conus
        WHERE ST_Intersects(geometry, ST_SetSRID(ST_GeomFromText('{SD_BBOX_5070}'), 5070))
        ORDER BY x, y
    """, limit=600)

    if not coord_result or not coord_result.get("data"):
        print("Failed to get tile coordinates!", flush=True)
        return []

    all_coords = [(r["x"], r["y"]) for r in coord_result["data"]]
    needed = [c for c in all_coords if c not in existing]
    print(f"Total tiles: {len(all_coords)}, need to download: {len(needed)}", flush=True)

    # Download in batches
    for i in range(0, len(needed), BATCH_SIZE):
        batch = needed[i:i + BATCH_SIZE]
        conditions = " OR ".join([f"(x = {x} AND y = {y})" for x, y in batch])
        print(f"  Batch {i // BATCH_SIZE + 1}: tiles {i + 1}-{min(i + BATCH_SIZE, len(needed))} of {len(needed)}...", flush=True)

        query = f"""
            SELECT x, y, base64(RS_AsGeoTiff(raster)) as raster_b64
            FROM org_catalog.wildfire_risk.burn_probability_conus
            WHERE {conditions}
        """
        result = execute_query(session_id, query, limit=BATCH_SIZE)

        if not result or not result.get("success") or not result.get("data"):
            print(f"  Failed batch, retrying with smaller batch...", flush=True)
            # Retry one at a time
            for x, y in batch:
                q = f"SELECT x, y, base64(RS_AsGeoTiff(raster)) as raster_b64 FROM org_catalog.wildfire_risk.burn_probability_conus WHERE x = {x} AND y = {y}"
                r = execute_query(session_id, q, limit=1)
                if r and r.get("data"):
                    for row in r["data"]:
                        save_tile(row)
            continue

        for row in result["data"]:
            save_tile(row)

        print(f"  Total on disk: {len(list(OUTPUT_DIR.glob('bp_tile_*.tif')))}", flush=True)

    return list(OUTPUT_DIR.glob("bp_tile_*.tif"))


def save_tile(row):
    x, y = row["x"], row["y"]
    b64_data = row["raster_b64"]
    b64_clean = re.sub(r'\s+', '', b64_data)
    raw = base64.b64decode(b64_clean)
    tile_path = OUTPUT_DIR / f"bp_tile_{x}_{y}.tif"
    tile_path.write_bytes(raw)


def mosaic_tiles(tile_files):
    print(f"\nMosaicing {len(tile_files)} tiles...", flush=True)
    src_files = []
    for f in sorted(tile_files):
        try:
            src_files.append(rasterio.open(f))
        except Exception as e:
            print(f"  Skipping {f}: {e}", flush=True)

    if not src_files:
        print("No valid tiles!", flush=True)
        return None

    mosaic, out_transform = merge(src_files)
    out_meta = src_files[0].meta.copy()
    out_meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": out_transform,
        "compress": "deflate",
    })

    print(f"  Shape: {mosaic.shape}, CRS: {out_meta.get('crs')}", flush=True)
    with rasterio.open(MERGED_OUTPUT, "w", **out_meta) as dest:
        dest.write(mosaic)

    for src in src_files:
        src.close()

    size_mb = MERGED_OUTPUT.stat().st_size / 1024 / 1024
    print(f"  Saved: {MERGED_OUTPUT} ({size_mb:.1f} MB)", flush=True)
    return MERGED_OUTPUT


def main():
    print("=== Extracting San Diego Burn Probability Rasters ===\n", flush=True)

    # If --mosaic-only flag, just mosaic existing tiles
    if "--mosaic-only" in sys.argv:
        tile_files = list(OUTPUT_DIR.glob("bp_tile_*.tif"))
        if tile_files:
            mosaic_tiles(tile_files)
        return

    session_id = init_session()
    tile_files = extract_tiles(session_id)

    if tile_files:
        mosaic_tiles(tile_files)
        print("\nDone!", flush=True)
    else:
        print("No tiles extracted!", flush=True)


if __name__ == "__main__":
    main()
