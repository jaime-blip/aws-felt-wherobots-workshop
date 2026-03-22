"""Discover all spatial tables, columns, row counts, and sample values."""
import psycopg2
import os

conn = psycopg2.connect(os.environ["AURORA_DSN"])
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
