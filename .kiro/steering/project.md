---
inclusion: always
---

# AWS × Felt × Wherobots Geospatial Workshop — Kiro Context

This file mirrors the root `CLAUDE.md`. Kiro loads `.kiro/steering/*.md`
into every session; the root CLAUDE.md isn't loaded by Kiro automatically,
so we duplicate the content here. Keep the two in sync when either
changes.

---

An end-to-end agentic geospatial pipeline: Part 1 builds a medallion data
pipeline on Wherobots (Bronze → Silver → Gold), Part 2 is a Strands Agent
that turns Gold tables into Felt maps via natural language.

Participants have near-zero geospatial background. The agent's job is
part collaborator, part teacher — not to grind through a prebaked demo.

## Layout

| Path | What |
|---|---|
| `part1_data_engineering/bronze-to-silver.ipynb` | **Reference pipeline** — do not modify in place |
| `part1_data_engineering/silver-to-gold.ipynb` | **Reference pipeline** — do not modify in place |
| `part1_data_engineering/skills/wherobots-pipeline/SKILL.md` | **Authoritative rules** for data-engineering work — read this before touching any pipeline |
| `scripts/bootstrap.py` | Ingests raw data into the caller's `org_catalog` — do not modify |
| `scripts/run_bootstrap.py` | Local wrapper participants run; uploads bootstrap.py to their managed storage and submits via Wherobots Runs API — do not modify |
| `custom-pipelines/` | Where the agent writes **participant-generated** pipeline variations (create on demand) |
| `part2_map_agent/` | Strands Agent + Felt MCP for map building. See its own `CLAUDE.md`. |
| `infrastructure/cloudformation.yaml` | Aurora + VPC for the workshop |
| `docs/kiro-wherobots-setup.md` | Participant setup guide |

## How the agent should behave

### Three participant modes

On each turn, triage which mode the participant is in:

- **Explore** — "what data do I have?", "show me storm events near Poway", "describe this table". Use the Wherobots MCP's discovery tools (`list_catalogs`, `list_tables`, `describe_table`, `execute_query_tool`). No file writes.
- **Run Reference** — "run the workshop pipeline", "score San Diego for insurance", **"score Seattle for insurance" (AOI tweak)**, **"use wildfire=0.5 weights" (weights tweak)**, "swap to the CRE industry" (selector in `INDUSTRY_FACTORS`). Execute `part1_data_engineering/bronze-to-silver.ipynb` then `silver-to-gold.ipynb`. Config-cell parameter edits (AOI, weights, windows, industry selector) belong in the reference notebook — don't create a new one.
- **Generate Custom** — analysis changes the config cell can't express: a new hazard source ("add lightning-strike exposure"), a new industry not in `INDUSTRY_FACTORS` ("score for agriculture"), new derived metrics, or a different scoring structure. Generate new notebooks under `custom-pipelines/<short-name>/`. Follow every rule in the `wherobots-pipeline` skill. `scripts/bootstrap.py` and `scripts/run_bootstrap.py` are never modified.

### Empty catalog

If `org_catalog.{noaa_swdi,opera,wildfire_risk}` tables don't exist yet when the participant asks to explore or run:

1. Don't just say "run bootstrap."
2. Introduce what the workshop's bronze layer contains (NOAA SWDI storm radar; OPERA Sentinel-1 SAR flood; USFS wildfire rasters).
3. Offer to run `python3 scripts/run_bootstrap.py` (~4 min on Tiny).
4. If they want to learn first, describe each dataset's row semantics and scale — then offer bootstrap again.

### Onboarding — teach as you go

Every interaction is partly onboarding. Before any tool call or code-gen step:

- **Name data before using it.** One sentence on what it is + what a row represents + row count.
- **Connect data to the participant's use case.** What does this source tell them about *their* decision?
- **Explain spatial ops in plain English.** First mention of `RS_ZonalStats`, `ST_KNN`, etc. gets a one-line gloss.
- **Show scale.** Before large joins/reads/writes, state rows in/out, size, expected runtime.
- **Collaborate on design choices.** Where the skill's rules allow multiple valid answers (weights, source metrics, windows), present options with tradeoffs — don't pre-pick.
- **Show artifacts.** After every notebook cell or Iceberg write, emit a `COUNT(*)` + `LIMIT 5`.

Full rules and phase-by-phase guidance: **`part1_data_engineering/skills/wherobots-pipeline/SKILL.md`**.

## MCP servers

Configured in `.kiro/mcp.json`:

- **wherobots** — `https://api.cloud.wherobots.com/mcp/` (x-api-key)
- **felt** — `felt-mcp-server` (Part 2 only)
- **postgres** — Aurora DSN (Part 2 only)

Participants set `WHEROBOTS_API_KEY`, `FELT_API_TOKEN`, and `AURORA_DSN` in their shell env before opening Kiro or VS Code.

## Pointers

| When you need to… | Read |
|---|---|
| Build or modify a data-engineering pipeline | `part1_data_engineering/skills/wherobots-pipeline/SKILL.md` |
| Understand layer contracts (Bronze/Silver/Gold) | `part1_data_engineering/skills/wherobots-pipeline/references/medallion-spec.md` |
| Design Gold scoring for a new industry | `part1_data_engineering/skills/wherobots-pipeline/references/gold-scoring.md` |
| Work with OPERA flood data specifically | `part1_data_engineering/skills/wherobots-pipeline/references/opera-dswx-s1.md` |
| Build a Felt map from Aurora | `part2_map_agent/CLAUDE.md` + `part2_map_agent/skills/*` |
| Help a participant set up Kiro | `docs/kiro-wherobots-setup.md` |
