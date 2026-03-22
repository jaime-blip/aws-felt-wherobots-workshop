# Aurora PostGIS — Data Discovery Skill

How to discover and query spatial data in Amazon Aurora PostgreSQL (PostGIS).

## Connection

```python
import psycopg2, os
conn = psycopg2.connect(os.environ["AURORA_DSN"])
cur = conn.cursor()
```

`psycopg2`, `os`, and `AURORA_DSN` are pre-loaded in your environment.

## Step 1: Find Spatial Tables

```python
conn = psycopg2.connect(os.environ["AURORA_DSN"])
cur = conn.cursor()
cur.execute("""
    SELECT table_schema, table_name, column_name
    FROM information_schema.columns
    WHERE udt_name = 'geometry'
      AND table_schema NOT IN ('pg_catalog','information_schema')
    ORDER BY table_schema, table_name
""")
for schema, table, geom_col in cur.fetchall():
    cur.execute(f"SELECT COUNT(*) FROM {schema}.{table}")
    count = cur.fetchone()[0]
    print(f"{schema}.{table} ({count} rows, geom: {geom_col})")
conn.close()
```

## Step 2: Inspect Columns

```python
conn = psycopg2.connect(os.environ["AURORA_DSN"])
cur = conn.cursor()
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'MY_TABLE'
    ORDER BY ordinal_position
""")
for col, dtype in cur.fetchall():
    if not col.startswith("felt:"):  # skip internal columns
        print(f"  {col}: {dtype}")
conn.close()
```

## Step 3: Sample Values (for styling decisions)

```python
conn = psycopg2.connect(os.environ["AURORA_DSN"])
cur = conn.cursor()

# Distinct values for categorical columns
cur.execute("SELECT DISTINCT my_column FROM public.my_table WHERE my_column IS NOT NULL LIMIT 15")
print([r[0] for r in cur.fetchall()])

# Numeric range for gradient styling
cur.execute("SELECT MIN(my_num), MAX(my_num), AVG(my_num) FROM public.my_table")
print(cur.fetchone())

# Preview rows
cur.execute("SELECT * FROM public.my_table LIMIT 3")
for row in cur.fetchall():
    print(row)
conn.close()
```

## Quick Discovery Script (all-in-one)

Use this to get a full picture of what's available:

```python
import psycopg2, os
conn = psycopg2.connect(os.environ["AURORA_DSN"])
cur = conn.cursor()

# Find all spatial tables
cur.execute("""
    SELECT c.table_schema, c.table_name, c.column_name, c.data_type
    FROM information_schema.columns c
    JOIN (
        SELECT table_schema, table_name
        FROM information_schema.columns WHERE udt_name = 'geometry'
    ) g ON c.table_schema = g.table_schema AND c.table_name = g.table_name
    WHERE c.table_schema = 'public'
      AND c.table_name NOT IN ('geometry_columns','geography_columns','spatial_ref_sys','raster_columns','raster_overviews')
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
    text_cols = [c[0] for c in info["cols"] if c[1] in ("text","character varying")]
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
SELECT * FROM public.my_table
WHERE ST_Within(geom, ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326))

-- Within distance (meters)
SELECT * FROM public.my_table
WHERE ST_DWithin(geom::geography, ST_MakePoint(lon, lat)::geography, 5000)

-- Centroid
SELECT ST_X(ST_Centroid(geom)) as lon, ST_Y(ST_Centroid(geom)) as lat
FROM public.my_table

-- Area
SELECT ST_Area(geom::geography) as area_sqm FROM public.my_table
```

## Tips
- ALWAYS discover schema before writing queries — never assume column names
- Filter out columns starting with `felt:` (internal metadata)
- Geometry column is usually `geom`
- Use `LIMIT` when previewing large tables
- Check distinct values on text columns to decide between categorical vs numeric styling
