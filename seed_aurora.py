#!/usr/bin/env python3
"""Seed building_risk table in Aurora PostgreSQL."""
import psycopg2, random, json
random.seed(42)

DSN = "postgresql://sales_engineers_user:ZwIZ5dUqaAwfUlgirLoStAHzIMrY0f99@dpg-cs6np65umphs73e7tkog-a.oregon-postgres.render.com/sales_engineers"
conn = psycopg2.connect(DSN)
cur = conn.cursor()

cur.execute("DROP TABLE IF EXISTS building_risk CASCADE")
cur.execute("""
    CREATE TABLE building_risk (
        asset_id TEXT PRIMARY KEY,
        geometry GEOMETRY(Point, 4326),
        city TEXT,
        flood_factor FLOAT,
        storm_factor FLOAT,
        wildfire_factor FLOAT,
        risk_score FLOAT,
        risk_category TEXT,
        dominant_hazard TEXT,
        score_explanation JSONB
    )
""")
conn.commit()

cities = {
    "Austin":      {"lat": (30.15, 30.40), "lon": (-97.85, -97.60), "fire": 0.7, "flood": 0.4, "storm": 0.5},
    "Houston":     {"lat": (29.55, 29.90), "lon": (-95.60, -95.25), "fire": 0.1, "flood": 0.85, "storm": 0.7},
    "Miami":       {"lat": (25.65, 25.95), "lon": (-80.35, -80.10), "fire": 0.05, "flood": 0.8, "storm": 0.75},
    "Los Angeles": {"lat": (33.90, 34.30), "lon": (-118.65, -118.10), "fire": 0.9, "flood": 0.15, "storm": 0.2},
}

for city, cfg in cities.items():
    batch = []
    for i in range(300):
        lat = random.uniform(*cfg["lat"])
        lon = random.uniform(*cfg["lon"])
        flood = round(random.uniform(0, cfg["flood"]), 3)
        storm = round(random.uniform(0, cfg["storm"]), 3)
        fire = round(random.uniform(0, cfg["fire"]), 3)
        score = round(0.4*flood + 0.3*storm + 0.3*fire, 3)
        cat = "critical" if score >= 0.5 else "high" if score >= 0.3 else "moderate" if score >= 0.15 else "low"
        dom = max([("flood",flood),("storm",storm),("wildfire",fire)], key=lambda x:x[1])[0]
        aid = f"{city.lower().replace(' ','_')}_{i:04d}"
        expl = json.dumps({"flood":flood,"storm":storm,"wildfire":fire,"weights":"0.4/0.3/0.3"})
        batch.append((aid, lon, lat, city, flood, storm, fire, score, cat, dom, expl))
    cur.executemany("""
        INSERT INTO building_risk VALUES (%s, ST_SetSRID(ST_MakePoint(%s,%s),4326), %s,%s,%s,%s,%s,%s,%s,%s)
    """, batch)
    conn.commit()
    print(f"  {city}: {len(batch)} rows")

cur.execute("CREATE INDEX idx_br_geom ON building_risk USING GIST (geometry)")
cur.execute("CREATE INDEX idx_br_city ON building_risk (city)")
conn.commit()
cur.execute("SELECT COUNT(*) FROM building_risk")
print(f"Total: {cur.fetchone()[0]} buildings seeded ✅")
conn.close()
