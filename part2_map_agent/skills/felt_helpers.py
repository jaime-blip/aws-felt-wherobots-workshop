"""
Felt Helper Functions
=====================
Reusable utilities for the Map Builder Agent's run_python tool.
Import with: from scripts.felt_helpers import *

These wrap common felt-python patterns with proper error handling,
polling, and FSL formatting.
"""

import os
import time
import json
from felt_python import (
    create_map,
    add_source_layer,
    list_layers,
    update_layer_style,
)

TOKEN = os.environ.get("FELT_API_TOKEN")
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "e5UKkPZxTwiR9CxbRzFw9AZA")


# ── Layer Processing ──────────────────────────────────────────

def wait_for_layer(map_id: str, timeout_s: int = 90, poll_interval: int = 3, expect_count: int = None) -> dict:
    """Poll until the newest layer on a map finishes processing.

    For multi-layer maps, pass expect_count to wait until that many
    layers are completed (e.g. if you just added layer #3, pass expect_count=3).

    Args:
        map_id: Felt map ID.
        timeout_s: Max seconds to wait (default 90).
        poll_interval: Seconds between polls (default 3).
        expect_count: Wait until this many layers are completed. If None,
                      waits until no layers are in 'processing' state.

    Returns:
        The most recently completed layer dict (with id, status, etc).

    Raises:
        TimeoutError: If layer doesn't complete in time.
        RuntimeError: If any layer processing fails.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        time.sleep(poll_interval)
        layers = list_layers(map_id=map_id, api_token=TOKEN)
        if not layers:
            continue

        completed = [l for l in layers if l.get("status") == "completed"]
        processing = [l for l in layers if l.get("status") == "processing"]
        failed = [l for l in layers if l.get("status") == "failed"]

        if failed:
            raise RuntimeError(f"Layer processing failed: {failed[0]}")

        if expect_count and len(completed) >= expect_count:
            print(f"  ✅ {len(completed)} layers completed")
            return completed[0]  # newest is first in the list
        elif not expect_count and not processing and completed:
            print(f"  ✅ {len(completed)} layers completed")
            return completed[0]
        else:
            print(f"  ... {len(completed)} done, {len(processing)} processing")
    raise TimeoutError(f"Layer not ready after {timeout_s}s")


# ── Map Creation Pipeline ─────────────────────────────────────

def create_map_with_sql(
    title: str,
    sql: str,
    style: dict = None,
    timeout_s: int = 60,
) -> dict:
    """Full pipeline: create map → add SQL layer → wait → style.

    Args:
        title: Map title.
        sql: SQL query against the Aurora source.
        style: Optional FSL style dict (must include version: "2.3.1").
        timeout_s: Max seconds to wait for layer processing.

    Returns:
        Dict with map_id, map_url, layer_id, status.
    """
    # Create map
    m = create_map(title=title, api_token=TOKEN)
    map_id = m["id"]
    map_url = m["url"]
    print(f"  Map created: {map_url}")

    # Add source layer
    params = {"from": "sql", "source_id": SOURCE_ID, "query": sql}
    add_source_layer(map_id=map_id, source_layer_params=params, api_token=TOKEN)
    print(f"  SQL layer added, waiting for processing...")

    # Wait for processing
    layer = wait_for_layer(map_id, timeout_s=timeout_s)
    layer_id = layer["id"]
    print(f"  Layer ready: {layer_id}")

    # Apply style
    if style:
        update_layer_style(
            map_id=map_id, layer_id=layer_id, style=style, api_token=TOKEN
        )
        print(f"  Style applied!")

    print(f"  🔗 {map_url}")
    return {
        "map_id": map_id,
        "map_url": map_url,
        "layer_id": layer_id,
        "status": "completed",
    }


# ── FSL Style Builders ───────────────────────────────────────

def categorical_style(
    attribute: str,
    categories: list = None,
    colors: list = None,
    display_names: dict = None,
    top_n: int = 10,
    size: int = 6,
    opacity: float = 0.9,
) -> dict:
    """Build a valid FSL categorical style.

    Args:
        attribute: Column name to categorize by.
        categories: Explicit list of category values. If None, uses top N.
        colors: Parallel list of hex colors. If None, uses palette shortcut.
        display_names: Dict mapping values to legend labels.
        top_n: Number of top categories if categories is None.
        size: Point/stroke size.
        opacity: Fill opacity.

    Returns:
        Valid FSL dict ready for update_layer_style().
    """
    if categories:
        cat_config = categories
    else:
        cat_config = {"type": "top", "count": top_n}

    paint = {
        "color": colors if colors else "@catPalette4",
        "size": size,
        "opacity": opacity,
        "strokeColor": "auto",
        "strokeWidth": 1,
    }

    legend = {}
    if display_names:
        legend["displayName"] = display_names

    return {
        "version": "2.3.1",
        "type": "categorical",
        "config": {
            "categoricalAttribute": attribute,
            "categories": cat_config,
            "showOther": True,
        },
        "paint": paint,
        "legend": legend,
    }


def numeric_style(
    attribute: str,
    palette: str = "@ylRed",
    size: list = None,
    opacity: float = 0.9,
) -> dict:
    """Build a valid FSL numeric (choropleth/graduated) style.

    Args:
        attribute: Numeric column name.
        palette: Color palette shortcut (e.g. "@ylRed", "@galaxy").
        size: [min, max] point size range. None for default.
        opacity: Fill opacity.

    Returns:
        Valid FSL dict.
    """
    paint = {
        "color": palette,
        "opacity": opacity,
        "strokeColor": "auto",
        "strokeWidth": 1,
    }
    if size:
        paint["size"] = size
    else:
        paint["size"] = [4, 20]

    return {
        "version": "2.3.1",
        "type": "numeric",
        "config": {
            "numericAttribute": attribute,
        },
        "paint": paint,
        "legend": {},
    }


# ── Database Discovery ────────────────────────────────────────

def discover_table(dsn: str, table_name: str) -> dict:
    """Discover schema, geometry, and sample values for a spatial table.

    Args:
        dsn: PostgreSQL connection string.
        table_name: Fully qualified table name (schema.table).

    Returns:
        Dict with columns, geom_col, text_cols, numeric_cols, row_count,
        and sample_values.
    """
    import psycopg2

    conn = psycopg2.connect(dsn)
    cur = conn.cursor()

    # Parse schema.table
    parts = table_name.split(".")
    if len(parts) == 2:
        schema, table = parts
    else:
        schema, table = "public", parts[0]

    # Get columns
    cur.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = %s AND table_name = %s
        ORDER BY ordinal_position
    """, (schema, table))
    columns = cur.fetchall()

    geom_col = next((c[0] for c in columns if c[1] == "USER-DEFINED"), None)
    text_cols = [c[0] for c in columns
                 if c[1] in ("text", "character varying") and c[0] != geom_col]
    numeric_cols = [c[0] for c in columns
                    if c[1] in ("double precision", "real", "integer",
                                "bigint", "numeric") and c[0] != geom_col]

    # Row count
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    row_count = cur.fetchone()[0]

    # Sample values for text columns
    sample_values = {}
    for col in text_cols[:5]:
        try:
            cur.execute(
                f'SELECT DISTINCT "{col}" FROM {table_name} '
                f'WHERE "{col}" IS NOT NULL LIMIT 10'
            )
            sample_values[col] = [r[0] for r in cur.fetchall()]
        except Exception:
            conn.rollback()

    conn.close()

    return {
        "table": table_name,
        "row_count": row_count,
        "geom_col": geom_col,
        "columns": [(c[0], c[1]) for c in columns if c[0] != geom_col],
        "text_cols": text_cols,
        "numeric_cols": numeric_cols,
        "sample_values": sample_values,
    }
