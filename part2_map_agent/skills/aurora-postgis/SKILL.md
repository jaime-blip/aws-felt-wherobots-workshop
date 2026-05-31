---
name: aurora-postgis
description: Fallback skill for direct Aurora PostgreSQL access via python_repl. Use when Felt MCP fails or for complex data transforms that can't be done in SQL.
allowed-tools: python_repl
---

# Aurora PostGIS — Fallback

**Primary path:** Use Felt MCP tools (`create_layer_from_data_source`, `get_tabular_data_from_data_source`) for all Aurora queries.

**Use this skill only when:**
- Felt MCP upload fails
- Complex data transforms that can't be done in SQL (pandas, geopandas)
- Debugging Aurora connectivity

## Fallback: Direct psycopg2 Access

```python
import psycopg2

conn = psycopg2.connect(AURORA_DSN)
cur = conn.cursor()

# Check connectivity
cur.execute("SELECT count(*) FROM workshop.insurance_exposure")
print(f"Row count: {cur.fetchone()[0]}")

# Sample query
cur.execute("""
    SELECT risk_tier, COUNT(*) as cnt
    FROM workshop.insurance_exposure
    GROUP BY risk_tier
    ORDER BY cnt DESC
""")
for row in cur.fetchall():
    print(row)

conn.close()
```

## Fallback: Upload via felt-python

If MCP upload fails, use felt-python directly:

```python
from felt_python import upload_file

# Upload a local GeoJSON file
result = upload_file(
    map_id="<map_id>",
    file_path="/tmp/data.geojson",
    api_token=FELT_TOKEN
)
print(f"Layer ID: {result['layer_id']}")
```

## Workshop Data (for reference)

The `workshop` schema contains:
- `workshop.insurance_exposure` — 1,035,306 buildings, insurance risk scores
- `workshop.cre_risk` — Commercial real estate risk scores
- `workshop.capital_markets_signals` — Capital markets signals (no risk_tier)
- `workshop.energy_asset_risk` — Energy infrastructure risk

## PostGIS Spatial Queries

```sql
-- Within distance (meters)
SELECT * FROM workshop.insurance_exposure
WHERE ST_DWithin(
    geometry::geography,
    ST_SetSRID(ST_MakePoint(-117.1611, 32.7157), 4326)::geography,
    16093.44  -- 10 miles
)

-- Buffer polygon
SELECT ST_Buffer(
    ST_SetSRID(ST_MakePoint(-117.1611, 32.7157), 4326)::geography,
    16093.44
)::geometry as geometry

-- Bounding box
SELECT * FROM workshop.insurance_exposure
WHERE ST_Within(geometry, ST_MakeEnvelope(-117.5, 32.5, -116.5, 33.0, 4326))
```

## When to Use This vs MCP

| Scenario | Use |
|----------|-----|
| Normal map creation | Felt MCP |
| SQL-backed layers | Felt MCP `create_layer_from_data_source` |
| Data exploration | Felt MCP `get_tabular_data_from_data_source` |
| MCP upload fails | python_repl + felt-python |
| Complex pandas/geopandas transforms | python_repl |
| Debugging connectivity | python_repl + psycopg2 |
