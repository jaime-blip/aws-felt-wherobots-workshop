# Meeting Prep — April 2, 2026 (Raj's Agenda)

Deck: https://docs.google.com/presentation/d/1qAiEdLfJEB4c5dYEAzQqFQ8LqhjAdxfern5xnH_wQ8k/edit?usp=share_link

---

## 1/ Presentation & Demo Ownership (from Notion meeting notes + deck structure)

**Event:** April 23, 2026 (two sessions: 2:45 PM UTC and 10:45 PM UTC)
**Format:** 60 min (45 min presentation+demo, 15 min workshop kickoff)
**Attendees get:** 72 hours after webinar to complete the workshop

### Speaker Assignments
- **Raj** (AWS) — Host, introductions
- **Jaime** (Felt) — Primary presenter, narrative, demo
- **Ben/Damien** (Wherobots) — Wherobots overview + demo
- **Saurabh + Rajesh** (AWS) — Workshop lead engineers
- **Jordan** (AWS) — Program manager, live polling
- **Eliza** (AWS ISV) — Contact slide, marketplace links
- **Patty** (AWS) — Industry messaging, distribution

### Deck Flow (~30 slides)

| Section | Speaker | Duration |
|---------|---------|----------|
| Abstract + Speaker intros | Raj | 2 min |
| Partnership & Contact info | Eliza | 2 min |
| **Opening demo hook** (California wildfire → risk map) | Jaime | 5 min |
| Live Poll #1 (GIS familiarity) | Jordan | 1 min |
| GIS Level-Set (what is GIS?) | Jaime | 2 min |
| Solution overview (Felt + Wherobots + AWS) | Jaime + Ben | 5 min |
| Industry problem statements (Insurance, CRE, CapMkts, Energy) | Jaime | 3 min |
| Architecture slide (medallion, AWS services) | Damion | 3 min |
| **Detailed demo** (full pipeline walkthrough) | Jaime + Ben | 15 min |
| Takeaways + AM guidance (how to identify opportunities) | Raj | 5 min |
| **Workshop kickoff** (QR code, what you'll build) | Sarab/Rajesh | 10 min |
| Appendix (additional industry detail) | — | — |

### Key Messaging
- Position as **data engineering platform** for geospatial, NOT "a GIS system"
- Be ready for: "How are you different from Esri?" → cloud-native architecture
- First 15 min critical for AMs before they drop off — front-load the business value
- Deck uses Felt template; architecture slide uses AWS template

---

## 2/ Workshop Status

### Ready
- Workshop guide with 6 hands-on Part 1 steps (MCP prompts, expected outputs) + 5 Part 2 steps (annotated agent prompts)
- Part 1 notebooks (bronze->silver, silver->gold) + wherobots-pipeline skill
- Part 2 Strands agent with 2 skills (aurora-postgis, felt-mapping) + 24 eval scenarios
- Gold layer: 4 tables, ~358K San Diego buildings each
- Data seeding script for CloudFormation (`data/seed/export_gold_tables.py`)
- All data in repo (burn probability rasters, flood GeoTIFFs)
- Felt skill documentation shared via GitHub
- Repo cleaned up and structured

### Remains
- CloudFormation template for Aurora + seed (Damion/Sarab)
- Felt API key provisioning model (Jaime to confirm internally)
- Update MCP config to use Felt's HTTP MCP server
- Final pass on workshop guide with screenshots of expected output at each step
- Convert to AWS Workshop Studio format (Damion)

---

## 3/ Story Arc

```
THE PROBLEM (2 min)
"Every insurer, energy company, and real estate firm has the same problem:
satellite data is everywhere, but turning it into a decision takes weeks
of hand-stitched pipelines."
--> ReGrid customer story: they had this problem, solved it with Felt + Wherobots

THE INSIGHT (1 min)
"What if the pipeline itself was agentic? And the visualization was too?"

THE ARCHITECTURE (3 min)
Two-part agentic stack:
  Part 1: MCP-driven data engineering (Wherobots) -- the data pipeline builds itself
  Part 2: Agent-driven map creation (Strands + Felt) -- ask a question, get a map

THE DEMO (25 min)
Part 1: "Generate a risk pipeline for San Diego buildings"
  --> MCP discovers data, generates notebooks, scores 358K buildings, exports to Aurora
Part 2: "Show me buildings with high wildfire risk"
  --> Agent reads skills, queries Aurora, creates styled Felt map, returns URL
Moment of magic: zoom into a neighborhood, toggle the burn probability raster layer,
see WHY those specific buildings scored high

THE WORKSHOP (5 min)
"You'll build this yourself in 90 minutes. Here's the QR code."

THE CALL TO ACTION (2 min)
"This stack runs on AWS services you already have.
Felt and Wherobots are on AWS Marketplace. Start a free trial today."
```

---

## 4/ Dry Run Requirements

- All demo queries tested end-to-end against San Diego data
- Felt maps pre-created as backup (in case live demo fails)
- 5-min recorded demo as fallback (Jaime mentioned recording one)
- Presentation deck finalized with speaker notes
- One full rehearsal with all speakers in sequence
- Timing check: does it fit in 60 min?

---

## 5/ Open Items from Sarab's Minutes

### Done
- [x] GitHub repo shared, team has access
- [x] Felt skill docs committed (24 scenarios)
- [x] San Diego chosen as focus city
- [x] Composite risk scoring across 4 industry verticals
- [x] JDBC decided and tested (~2-3 min for all tables)
- [x] Skills/docs for Felt styling, Wherobots catalog, scoring
- [x] Repo cleaned up
- [x] Data seeding script ready for CloudFormation

### Remaining
- [ ] CloudFormation template for Aurora + seed data (Damion/Sarab)
- [ ] Felt API key sharing model: confirm with Felt team (pre-provision vs self-signup)
- [ ] Update workshop MCP config to include Felt HTTP MCP server
- [ ] Screenshots of expected output at each workshop step
- [ ] AWS Workshop Studio conversion (Damion)
- [ ] Test smaller/cheaper LLMs for Wherobots MCP (Pranav)

### Explicitly Deferred
- ElastiCache for caching -- out of scope for 90-min workshop
- Vector embedding / hybrid search -- optional, not core
- H3 hexagonal grid -- staying with building-level scoring
- Standard IO MCP -- using HTTP MCP only

---

## 6/ Attendee Takeaways + Opportunity Discovery

### Takeaways
- A working GitHub repo they can deploy in their own AWS account
- Understanding of MCP-driven data engineering (Wherobots)
- Understanding of agent-driven map creation (Strands + Felt)
- A Felt map they built themselves with real satellite-derived risk data

### Discovery / Qualify / Engage
- Post-workshop survey: "Which use case resonates? Insurance, CRE, Energy, CapMarkets?"
- "Do you have geospatial data you'd like to score this way?"
- Felt free trial + Wherobots free trial via AWS Marketplace
- AWS SA follow-up for Aurora/Bedrock architecture review
- Offer: "We'll run this workshop for your team with YOUR data"

---

## 7/ Opening Demo, Poll Questions, Call to Action

### Opening Demo (30 seconds, before any slides)
Live: type "Show me buildings at high wildfire risk in San Diego" --> Felt map appears in ~30s.
"That's what we're building today."

### Poll Questions (Slido or similar)
1. "What's your primary geospatial challenge?"
   - Data engineering / Visualization / Risk scoring / All of the above
2. "Which industry are you focused on?"
   - Insurance / Real Estate / Energy / Agriculture / Other
3. "How do you currently build geospatial pipelines?"
   - Manual scripts / No pipeline yet / Commercial tools / Open source

### Call to Action
- QR code --> workshop repo (self-service)
- QR code --> Felt free trial (Marketplace)
- QR code --> Wherobots free trial (Marketplace)
- "Email [contact] to schedule a guided workshop with your data"

---

## Bonus Idea: Full-Loop Agent Demo

Jaime's idea: What if the agent could handle the FULL pipeline in one prompt?

```
User: "Find wildfire risk for buildings near Ramona, score them, push to Aurora, and create a map"
  --> Agent uses Wherobots MCP to query burn probability
  --> Writes scored results to Aurora via JDBC
  --> Creates a Felt map with the results
  --> Returns a shareable URL
```

This would collapse the Part 1 / Part 2 divide into a single agent flow.
Could be the "closing demo" moment — after attendees have done both parts separately,
show them what it looks like when one agent orchestrates the entire stack.

Pros: Very impressive, shows the full agentic vision
Cons: Complex to build reliably, longer latency, more failure modes
Recommendation: Build it as a demo-only flow (not in workshop steps), test it heavily

---

## Felt MCP Server — CONFIRMED

**URL: `https://felt.com/mcp`**

Visible in Claude.ai → Customize → Connectors → Felt Maps (Custom).
OAuth-based — users authorize via Felt, then the MCP tools are available.

Tools: create_map, get_map, get_map_layers, update_layer_style, import_layer_from_url, upsert_elements, browse_data_sources, create_layer_from_data_source, get_sql_guidance, etc.

**MCP config for workshop (Claude Desktop / Kiro):**
```json
{
  "mcpServers": {
    "wherobots": {
      "url": "https://api.cloud.wherobots.com/mcp/",
      "headers": { "X-API-Key": "${WHEROBOTS_API_KEY}" }
    },
    "felt": {
      "url": "https://felt.com/mcp",
      "headers": { "Authorization": "Bearer ${FELT_API_TOKEN}" }
    }
  }
}
```
