# Webinar Demo Script — Insurance Risk Assessment

**Persona:** You are a **Risk Analytics Lead** at a property insurance company. Your team underwrites policies across San Diego County. After the devastating 2003 Cedar Fire and 2007 Witch Creek Fire, your company needs to reassess wildfire exposure for 1M insured properties. You have satellite imagery, NOAA weather events, and flood data — but it's all raw. You need to turn it into actionable risk scores.

---

## Query 1: Wherobots — Large-Scale Raster + Vector Join (Part 1)

**What you're showing:** Processing 1M building footprints against burn probability raster data at scale. This is the heavy-duty OLAP operation that PostGIS can't do efficiently.

**Narrative:** *"First, we need to score every building in San Diego for wildfire risk. We have satellite-derived burn probability data from the US Forest Service — this is a 32GB raster covering the entire continental US. We need to extract the burn probability value at every building footprint. That's a zonal statistics operation across 1M polygons against high-res raster tiles."*

**In Wherobots MCP (Kiro), say:**

> "Run zonal statistics on the San Diego buildings against the USFS burn probability raster. For each building, extract the mean burn probability from the underlying raster tiles."

**What happens:** Wherobots runs `RS_ZonalStats` on Apache Sedona — joins 1M Overture building polygons with ~500 burn probability raster tiles. This is where Wherobots shines: raster-vector joins at scale that would take hours in PostGIS take minutes on distributed Sedona.

**Talking point:** *"This is exactly the kind of operation where PostGIS hits a wall. PostGIS is brilliant for transactional queries — give me buildings within 5km of this point. But when you need to join a raster dataset with hundreds of thousands of polygons, you need a distributed processing engine. That's Wherobots."*

---

## Query 2: PostGIS on Aurora — Spatial Analysis for the Underwriter

**What you're showing:** Now that the scored data is in Aurora, an underwriter asks real business questions using PostGIS spatial functions.

**Narrative:** *"Great — our data engineers have processed the satellite data and scored every building. The Gold tables are in Aurora PostgreSQL with PostGIS. Now I'm the underwriter. I just got a new batch of policy applications from the Poway area — right at the wildland-urban interface where the Witch Creek Fire burned. I need to assess the risk."*

**Query to run (or prompt the agent with):**

```sql
-- "Which of my insured buildings near Poway have elevated wildfire exposure?"
SELECT 
    asset_id,
    ROUND(risk_score::numeric, 3) AS risk_score,
    ROUND(wildfire_factor::numeric, 3) AS wildfire_factor,
    ROUND(flood_factor::numeric, 3) AS flood_factor,
    risk_tier,
    ST_AsText(ST_Centroid(geometry)) AS location
FROM workshop.insurance_exposure
WHERE ST_DWithin(
    geometry::geography, 
    ST_SetSRID(ST_MakePoint(-117.0417, 32.9628), 4326)::geography, 
    5000  -- 5km radius around Poway
)
AND wildfire_factor > 0.3
ORDER BY wildfire_factor DESC
LIMIT 20;
```

**What this shows:**
- `ST_DWithin` — spatial buffer around Poway (5km radius)
- Filtering by `wildfire_factor > 0.3` — buildings with meaningful fire exposure
- The results show the wildland-urban interface buildings where fire risk is concentrated

**Talking point:** *"See how some buildings have a wildfire factor of 0.96 while their neighbor is at 0.01? That's because the burn probability raster has high resolution — one building sits on dry chaparral, the other is shielded by a ridge. This is real satellite-derived data, not a zip code average. That's the difference between 'this zip code has fire risk' and 'THIS building has fire risk.'"*

**Bonus spatial query — portfolio exposure summary:**

```sql
-- "What's my total exposure by risk tier within 10km of the Poway fire zone?"
SELECT 
    risk_tier,
    COUNT(*) AS buildings,
    ROUND(AVG(risk_score)::numeric, 3) AS avg_score,
    ROUND(AVG(wildfire_factor)::numeric, 3) AS avg_wildfire,
    ROUND(MAX(wildfire_factor)::numeric, 3) AS max_wildfire
FROM workshop.insurance_exposure
WHERE ST_DWithin(
    geometry::geography,
    ST_SetSRID(ST_MakePoint(-117.0417, 32.9628), 4326)::geography,
    10000  -- 10km
)
GROUP BY risk_tier
ORDER BY avg_score DESC;
```

---

## Query 3: Felt Map — Visualize the Underwriter's View

**What you're showing:** Turn the query results into an interactive map that the whole team can use.

**Narrative:** *"Now I need to share this with my team — the actuaries, the claims adjusters, the VP. They're not going to run SQL queries. They need a map. Let me ask the AI agent to build one."*

**Prompt to the Strands agent:**

> "Create a map called 'Poway Wildfire Exposure — Q2 2026 Review'. Add the insurance exposure buildings within 10km of Poway that have wildfire_factor above 0.1. Color them by risk_tier — red for high, orange for elevated, yellow for moderate, green for low. Add the burn probability raster as a background layer."

**Or if running the agent directly:**

```bash
./run.sh "Build me an insurance risk map focused on the Poway wildfire zone. Show buildings within 10km of Poway colored by risk tier. Use red for high risk, orange for elevated, yellow for moderate."
```

**What this produces:** A shareable Felt map URL with:
- 8,000+ building polygons around Poway
- Color-coded by risk tier
- Hoverable popups showing risk_score, wildfire_factor, flood_factor
- The 140 elevated-risk buildings clearly visible in the eastern hills

**Talking point:** *"This is the full loop. Satellite data → Wherobots processing → Aurora PostGIS → AI agent → interactive map. The underwriter didn't write any code. The data engineer used natural language with the Wherobots MCP. And the whole team can now collaborate on this map in Felt — draw on it, annotate, filter, share with stakeholders."*

---

## The 3-Query Flow (Summary for slides)

| # | What | Where | Why |
|---|------|-------|-----|
| 1 | Raster-vector join: 1M buildings × burn probability tiles | **Wherobots** (Sedona) | Large-scale OLAP spatial processing |
| 2 | Spatial buffer + filter: "Show me risky buildings near Poway" | **Aurora PostGIS** | Transactional OLTP spatial queries |
| 3 | Generate interactive risk map for the team | **Felt** (via AI agent) | Collaborative visualization + sharing |

**Key message:** Each tool does what it's best at. Wherobots processes at scale. PostGIS serves fast, indexed queries. Felt makes it visual and collaborative. The AI agent ties them together.
