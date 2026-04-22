# Webinar Demo Script — Insurance Risk Assessment

**Persona:** You are a **Risk Analytics Lead** at a property insurance company. Your team underwrites policies across San Diego County. It's been a devastating start to 2026: on New Year's Day, an atmospheric river dumped 2.5 inches of rain in 48 hours, overflowing the San Diego River, forcing 10+ water rescues in Mission Valley, and breaking rainfall records from Poway to El Cajon. Then in March, another round of flooding hit — we captured satellite flood extent data from March 5-11 using NASA's OPERA system. On March 3, FEMA updated the official flood maps for San Diego, Santee, Poway, and El Cajon. Your job: reassess flood AND wildfire exposure for 1M insured properties, using real 2026 satellite data.

---

## The Hook (30 seconds)

*"Six weeks ago, San Diego flooded. FEMA just redrew the flood maps. And we're heading into wildfire season with the same dry brush that fueled the Cedar and Witch Creek fires. Our question today: for 1 million insured buildings, which ones are actually at risk — and can we answer that question in under 90 minutes, from raw satellite data to an interactive risk map?"*

---

## Query 1: Wherobots — Large-Scale Raster + Vector Join (Part 1)

**What you're showing:** Processing 1M building footprints against burn probability raster data AND real 2026 flood satellite imagery at scale.

**Narrative:** *"We have three types of satellite data we need to join with our building footprints. First: US Forest Service burn probability — a 32GB raster covering the entire continental US. Second: NASA OPERA flood extent imagery from the March 2026 San Diego flooding — actual satellite captures showing which areas were underwater. Third: NOAA severe weather events — hail, mesocyclone, tornado vortex signatures. We need to extract values from all of these at every one of our 1 million building polygons. That's a zonal statistics operation at massive scale."*

**In Wherobots MCP (Kiro), say:**

> "Run zonal statistics on the San Diego buildings against the USFS burn probability raster and the March 2026 OPERA flood extent tiles. For each building, extract the mean burn probability and the maximum flood extent across the March 5-11 observation window."

**What happens:** Wherobots runs `RS_ZonalStats` on Apache Sedona — joins 1M Overture building polygons with ~500 burn probability raster tiles AND 7 days of flood rasters. This is where Wherobots shines: raster-vector joins at scale that would take hours in PostGIS take minutes on distributed Sedona.

**Talking point:** *"This is real satellite data from 6 weeks ago. Not a hypothetical. These flood tiles show us which neighborhoods were actually underwater during the March storms. And the burn probability data shows us which areas are primed for the next wildfire. PostGIS is amazing for transactional spatial queries, but when you need to join raster imagery with a million polygons, you need a distributed processing engine. That's Wherobots."*

---

## Query 2: PostGIS on Aurora — The Underwriter's Questions

**What you're showing:** Now that the scored data is in Aurora, an underwriter asks real business questions using PostGIS spatial functions.

**Narrative:** *"OK — our data engineers have processed the satellite data and scored every building. The Gold tables are in Aurora PostgreSQL with PostGIS. Now I'm the underwriter. I just got two urgent requests. First: which buildings in our portfolio were actually in the flood zone during the March event? Second: Poway just had its flood maps redrawn by FEMA — I need to reassess wildfire exposure for every policy in that area before renewal season."*

**Query 2a — Flood exposure from the March 2026 event:**

```sql
-- "Which insured buildings had actual flood exposure in March 2026?"
SELECT 
    risk_tier,
    COUNT(*) AS buildings,
    ROUND(AVG(flood_factor)::numeric, 3) AS avg_flood,
    ROUND(MAX(flood_factor)::numeric, 3) AS max_flood,
    ROUND(AVG(risk_score)::numeric, 3) AS avg_overall_risk
FROM workshop.insurance_exposure
WHERE flood_factor > 0.1
GROUP BY risk_tier
ORDER BY avg_flood DESC;
```

**Talking point:** *"See that one building scoring 'high'? flood_factor of 1.0 — it was directly in the flood path. But the real story is the 'moderate' tier: thousands of buildings that most people wouldn't consider flood-prone, but our satellite data says otherwise. This is why zip code averages don't work for insurance — you need building-level precision."*

**Query 2b — Spatial buffer around Poway's wildfire zone:**

```sql
-- "Show me the wildfire-exposed buildings near Poway"
SELECT 
    asset_id,
    ROUND(risk_score::numeric, 3) AS risk_score,
    ROUND(wildfire_factor::numeric, 3) AS wildfire,
    ROUND(flood_factor::numeric, 3) AS flood,
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

**Talking point:** *"Look at this — buildings with a wildfire factor of 0.96 sitting right next to buildings at 0.01. Same neighborhood, completely different risk profiles. That's because the burn probability raster has 30-meter resolution — one building sits on dry chaparral on a south-facing slope, the other is shielded by a ridge. This is the difference between 'this zip code has fire risk' and 'THIS building has fire risk.' And now with the March floods AND the new FEMA maps, some of these same buildings face compound risk — fire AND flood."*

---

## Query 3: Felt Map — Share with the Team

**What you're showing:** Turn the analysis into an interactive map the whole team can use — no code required.

**Narrative:** *"I need to share this with the team — actuaries, claims adjusters, the VP. They're not going to run SQL. They need a map they can click around in, filter, annotate, and share with our reinsurer. One prompt."*

**Prompt to the Strands agent:**

> "Create a map called 'San Diego Risk Review — Post-March 2026 Floods'. Add two layers: first, all buildings with flood_factor above 0.1, colored by flood intensity from blue (low) to dark blue (high). Second, all buildings near Poway with wildfire_factor above 0.3, colored red to orange by wildfire severity. Title the layers 'March 2026 Flood Exposure' and 'Poway Wildfire Zone'."

**What this produces:** A shareable Felt map URL with:
- Flood-exposed buildings across San Diego (from real March 2026 satellite data)
- Wildfire-exposed buildings in the Poway zone
- Hoverable popups showing risk_score, wildfire_factor, flood_factor per building
- The team can filter, annotate, draw on it, share the URL

**Talking point:** *"This is the full loop. Satellite data captured 6 weeks ago → Wherobots processing at scale → Aurora PostGIS for underwriter queries → AI agent → interactive map. The underwriter didn't write any code. The data engineer used natural language with the Wherobots MCP. And now the whole team — actuaries, claims, legal — can collaborate on this map in Felt. Draw circles around areas of concern, annotate individual buildings, filter by risk tier, share the link with your reinsurer. Real data, real flood, real decisions."*

---

## The 3-Query Flow (Summary for slides)

| # | What | Where | Why | Data |
|---|------|-------|-----|------|
| 1 | Raster-vector join: 1M buildings × burn probability + flood tiles | **Wherobots** (Sedona) | Large-scale OLAP spatial processing | USFS burn probability (32GB) + OPERA flood March 2026 + NOAA weather |
| 2 | Spatial buffer + filter: "Which buildings flooded? What's at risk near Poway?" | **Aurora PostGIS** | Fast transactional OLTP spatial queries | Scored Gold tables (1M rows × 4 industry verticals) |
| 3 | Generate interactive risk map for the team | **Felt** (via AI agent) | Collaborative visualization + sharing | Source layers from Aurora, real-time |

**Key message:** Each tool does what it's best at. Wherobots processes satellite imagery at scale. PostGIS serves fast, indexed spatial queries. Felt makes it visual and collaborative. The AI agent ties them together. And this isn't hypothetical — this is real 2026 flood data from 6 weeks ago.
