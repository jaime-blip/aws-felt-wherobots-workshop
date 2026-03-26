#!/usr/bin/env python3
"""Extract MODIS flood rasters from Wherobots MCP, mosaic per date, upload to Felt."""

import base64
import json
import os
import re
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
import requests

WB_MCP_URL = "https://api.cloud.wherobots.com/mcp"
WB_API_KEY = os.environ.get("WHEROBOTS_API_KEY", "19e484ca-8088-4b22-b920-f0600a64dc26")

SD_BBOX = "POLYGON((-117.4 32.5, -116.8 32.5, -116.8 33.1, -117.4 33.1, -117.4 32.5))"
OUTPUT_DIR = Path("data/flood_rasters")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
    "X-API-Key": WB_API_KEY,
}
BATCH_SIZE = 20


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
        "clientInfo": {"name": "extract-flood", "version": "1.0"},
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


def main():
    print("=== Extracting MODIS Flood Rasters for San Diego ===\n", flush=True)

    session_id = init_session()

    # Get all tile coords
    coord_result = execute_query(session_id, f"""
        SELECT x, y, acq_date FROM org_catalog.modis.MCDWD_L3_F3_NRT
        WHERE ST_Intersects(geometry, ST_GeomFromText('{SD_BBOX}', 4326))
        ORDER BY acq_date, x, y
    """, limit=200)

    if not coord_result or not coord_result.get("data"):
        print("No tiles found!", flush=True)
        return

    all_tiles = coord_result["data"]
    print(f"Total tiles: {len(all_tiles)}", flush=True)

    # Group by date
    dates = {}
    for t in all_tiles:
        d = t["acq_date"]
        if d not in dates:
            dates[d] = []
        dates[d].append((t["x"], t["y"]))

    for date_ms, coords in sorted(dates.items()):
        from datetime import datetime, timezone
        date_str = datetime.fromtimestamp(date_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        print(f"\nDate {date_str}: {len(coords)} tiles", flush=True)

        tile_files = []
        for i in range(0, len(coords), BATCH_SIZE):
            batch = coords[i:i + BATCH_SIZE]
            conditions = " OR ".join([f"(x = {x} AND y = {y})" for x, y in batch])
            print(f"  Batch {i // BATCH_SIZE + 1}...", flush=True)

            query = f"""
                SELECT x, y, base64(RS_AsGeoTiff(raster)) as raster_b64
                FROM org_catalog.modis.MCDWD_L3_F3_NRT
                WHERE acq_date = CAST({date_ms} / 1000 AS TIMESTAMP)
                AND ({conditions})
            """
            # Use epoch filter differently - use the raw value
            query = f"""
                SELECT x, y, base64(RS_AsGeoTiff(raster)) as raster_b64
                FROM org_catalog.modis.MCDWD_L3_F3_NRT
                WHERE acq_date = DATE '{date_str}'
                AND ({conditions})
            """

            result = execute_query(session_id, query, limit=BATCH_SIZE)
            if not result or not result.get("success") or not result.get("data"):
                print(f"  Failed batch, skipping", flush=True)
                continue

            for row in result["data"]:
                x, y = row["x"], row["y"]
                b64_clean = re.sub(r'\s+', '', row["raster_b64"])
                raw = base64.b64decode(b64_clean)
                tile_path = OUTPUT_DIR / f"flood_{date_str}_{x}_{y}.tif"
                tile_path.write_bytes(raw)
                tile_files.append(tile_path)

        if not tile_files:
            continue

        # Mosaic this date
        print(f"  Mosaicing {len(tile_files)} tiles...", flush=True)
        srcs = []
        for f in tile_files:
            try:
                srcs.append(rasterio.open(f))
            except Exception as e:
                print(f"  Skip {f}: {e}", flush=True)

        if not srcs:
            continue

        mosaic, out_transform = merge(srcs)
        meta = srcs[0].meta.copy()
        meta.update({
            "driver": "GTiff", "height": mosaic.shape[1], "width": mosaic.shape[2],
            "transform": out_transform, "compress": "deflate",
        })

        out_path = OUTPUT_DIR / f"flood_sandiego_{date_str}.tif"
        with rasterio.open(out_path, "w", **meta) as dst:
            dst.write(mosaic)
        for s in srcs:
            s.close()

        # Clean up individual tiles
        for f in tile_files:
            f.unlink(missing_ok=True)

        print(f"  Saved: {out_path} ({out_path.stat().st_size / 1024 / 1024:.1f} MB)", flush=True)

    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
