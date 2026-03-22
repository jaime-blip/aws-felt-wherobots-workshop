# Aurora PostGIS Skill

Query data from Amazon Aurora PostgreSQL (PostGIS) to understand what's available for mapping.

## Connection

```python
import psycopg2, os
conn = psycopg2.connect(os.environ["AURORA_DSN"])
cur = conn.cursor()
```

## Discovering Data

### List schemas and tables with geometry:
```python
cur.execute("""
    SELECT table_schema, table_name, column_name
    FROM information_schema.columns
    WHERE udt_name = 'geometry'
      AND table_schema NOT IN ('pg_catalog','information_schema')
    ORDER BY table_schema, table_name
""")
for schema, table, geom_col in cur.fetchall():
    print(f"{schema}.{table} (geom: {geom_col})")
```

### Inspect a table's columns:
```python
cur.execute("""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'building_risk'
    ORDER BY ordinal_position
""")
```

### Preview data:
```python
cur.execute("SELECT * FROM public.building_risk LIMIT 5")
```

### Get row count:
```python
cur.execute("SELECT COUNT(*) FROM public.building_risk")
```

### Get distinct values (for categorical columns):
```python
cur.execute("SELECT DISTINCT risk_category FROM public.building_risk")
```

### Get numeric range (for gradient styling):
```python
cur.execute("SELECT MIN(risk_score), MAX(risk_score), AVG(risk_score) FROM public.building_risk")
```

## Available Schemas

| Schema | Domain | Key tables |
|--------|--------|------------|
| public | Climate risk + schools | building_risk, schools_in_victoria_australia |
| shoprite | Retail locations + demographics | locations (has geom) |
| real_estate | NJ parcels, sales, land cover | newjersey_parcels_mod4, past_sales, vacant_parcels_w_landcover |
| broadband | CA infrastructure | power_plants_ca, ca_cities |
| full_stack_demo | Solar analysis | solar_potential_queries |

## Spatial Queries (PostGIS)

```sql
-- Bounding box filter
SELECT * FROM table WHERE ST_Within(geom, ST_MakeEnvelope(xmin, ymin, xmax, ymax, 4326))

-- Distance filter (meters)
SELECT * FROM table WHERE ST_DWithin(geom::geography, ST_MakePoint(lon, lat)::geography, 5000)

-- Centroid
SELECT ST_X(ST_Centroid(geom)) as lon, ST_Y(ST_Centroid(geom)) as lat FROM table

-- Area in sq meters
SELECT ST_Area(geom::geography) FROM table
```

## Tips
- Always discover the schema first before writing queries
- Check column types to decide how to style (categorical vs numeric)
- Use LIMIT when previewing large tables
- Geometry column is usually `geom` or `geometry`
