---
name: aurora-postgis
description: Discover and query spatial data in Amazon Aurora PostgreSQL with PostGIS. Use when the user asks what data is available, or before building any map.
allowed-tools: python_repl file_read
---

# Aurora PostGIS — Data Discovery

How to discover and query spatial data in Amazon Aurora PostgreSQL with PostGIS.

## Connection

```python
import psycopg2, os
conn = psycopg2.connect(AURORA_DSN)
cur = conn.cursor()
# ... queries ...
conn.close()
```

`psycopg2`, `os`, and `AURORA_DSN` are pre-loaded in your environment.

## Important: Workshop Data

The `workshop` schema contains the Gold layer risk tables from Part 1:
- `workshop.insurance_exposure` — Insurance risk scores (358K buildings)
- `workshop.cre_risk` — Commercial real estate risk scores
- `workshop.capmarkets_signals` — Capital markets signals
- `workshop.energy_infra_risk` — Energy infrastructure risk

When querying via **psycopg2** (data discovery), use the full schema prefix:
```sql
SELECT * FROM workshop.insurance_exposure WHERE risk_tier = 'Critical'
```

When querying via **Felt source layers** (`add_source_layer`), ALWAYS use the `workshop.` schema prefix:
```sql
SELECT * FROM workshop.insurance_exposure WHERE risk_tier = 'Critical'
```
⚠️ Bare table names without the schema prefix will FAIL.

## Step 1: Find All Spatial Tables

```python
conn = psycopg2.connect(AURORA_DSN)
cur = conn.cursor()
cur.execute("""
    SELECT table_schema, table_name, column_name
    FROM information_schema.columns
    WHERE udt_name = 'geometry'
      AND table_schema NOT IN ('pg_catalog', 'information_schema')
    ORDER BY table_schema, table_name
""")
for schema, table, geom_col in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
    count = cur.fetchone()[0]
    print(f"{schema}.{table} ({count} rows, geom: {geom_col})")
conn.close()
```

## Step 2: Inspect a Table's Columns

```python
conn = psycopg2.connect(AURORA_DSN)
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = %s AND table_name = %s
    ORDER BY ordinal_position
""", ('public', 'your_table_here'))
for col, dtype in cur.fetchall():
    if not col.startswith("felt:"):  # skip internal metadata columns
        print(f"  {col}: {dtype}")
conn.close()
```

## Step 3: Sample Values (for styling decisions)

```python
conn = psycopg2.connect(AURORA_DSN)
cur = conn.cursor()

# Distinct values — use for categorical styling
cur.execute('SELECT DISTINCT "column_name" FROM schema.table WHERE "column_name" IS NOT NULL LIMIT 15')
print([r[0] for r in cur.fetchall()])

# Numeric range — use for gradient/numeric styling
cur.execute('SELECT MIN("column_name"), MAX("column_name"), AVG("column_name") FROM schema.table')
print(cur.fetchone())

# Preview a few rows
cur.execute("SELECT * FROM schema.table LIMIT 3")
for row in cur.fetchall():
    print(row)
conn.close()
```

## Quick Discovery (all-in-one)

Run the script at `scripts/discover_tables.py` or use this pattern:

```python
import psycopg2, os
conn = psycopg2.connect(AURORA_DSN)
cur = conn.cursor()

cur.execute("""
    SELECT c.table_schema, c.table_name, c.column_name, c.data_type
    FROM information_schema.columns c
    JOIN (
        SELECT table_schema, table_name
        FROM information_schema.columns WHERE udt_name = 'geometry'
    ) g ON c.table_schema = g.table_schema AND c.table_name = g.table_name
    WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema')
      AND c.table_name NOT IN ('geometry_columns', 'geography_columns',
                               'spatial_ref_sys', 'raster_columns', 'raster_overviews')
    ORDER BY c.table_schema, c.table_name, c.ordinal_position
""")

tables = {}
for schema, table, col, dtype in cur.fetchall():
    key = f"{schema}.{table}"
    if key not in tables:
        tables[key] = {"cols": [], "geom": None}
    if dtype == "USER-DEFINED":
        tables[key]["geom"] = col
    elif not col.startswith("felt:"):
        tables[key]["cols"].append((col, dtype))

for tbl, info in tables.items():
    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
    cnt = cur.fetchone()[0]
    text_cols = [c[0] for c in info["cols"] if c[1] in ("text", "character varying")]
    print(f"\n{tbl} ({cnt} rows, geom: {info['geom']})")
    print(f"  Columns: {', '.join(c[0] for c in info['cols'][:12])}")
    for col in text_cols[:3]:
        cur.execute(f'SELECT DISTINCT "{col}" FROM {tbl} WHERE "{col}" IS NOT NULL LIMIT 8')
        vals = [str(r[0])[:40] for r in cur.fetchall()]
        if vals:
            print(f"  {col}: {', '.join(vals)}")
conn.close()
```

## PostGIS Spatial Queries

```sql
-- Bounding box filter
SELECT * FROM schema.table
WHERE ST_Within(geom, ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326))

-- Within distance (meters)
SELECT * FROM schema.table
WHERE ST_DWithin(geom::geography, ST_MakePoint(lon, lat)::geography, 5000)

-- Centroid of each feature
SELECT *, ST_X(ST_Centroid(geom)) as lon, ST_Y(ST_Centroid(geom)) as lat
FROM schema.table

-- Area in square meters
SELECT *, ST_Area(geom::geography) as area_sqm FROM schema.table

-- Spatial join (e.g. points in polygons)
SELECT a.*, b.name AS containing_region
FROM schema.points a
JOIN schema.polygons b ON ST_Within(a.geom, b.geom)
```

## Tips
- ALWAYS discover the schema before writing queries — never assume column names
- Filter out columns starting with `felt:` (internal metadata)
- Geometry column is usually `geom` but always verify
- Use `LIMIT` when previewing large tables
- Check distinct values on text columns → categorical styling
- Check min/max on numeric columns → gradient/numeric styling
