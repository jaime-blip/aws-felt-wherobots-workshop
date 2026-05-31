# Part 2 — Map Builder AI Agent

See the root `CLAUDE.md` for the full project overview.

## Quick Reference

- **Agent**: `agent.py` — Strands Agent (Bedrock Claude) with Felt MCP tools + python_repl fallback
- **Skills**: `skills/felt-mapping/` (MCP tool docs) and `skills/aurora-postgis/` (fallback)
- **Run**: `./run.sh "your prompt"` or `./run.sh` for interactive mode

## Architecture

```
User prompt → Strands Agent → Felt MCP tools → Aurora (SQL) → Felt Map
                           ↘ python_repl (fallback for complex transforms)
```

**Primary path (Felt MCP):**
1. `list_data_sources` → find Aurora connection
2. `create_map` → new map
3. `create_layer_from_data_source` → SQL query
4. `poll_layer_processing_status` → wait
5. `generate_fsl` → AI styling
6. `update_layer_properties` → apply style
7. `render_map` → inline preview

**Fallback (python_repl):**
- MCP upload fails → `felt_python.upload_file()`
- Complex transforms → pandas/geopandas
- Debug connectivity → psycopg2

## Data (pre-loaded in Aurora, `workshop` schema)

4 Gold tables, ~1M San Diego buildings each:
- `workshop.insurance_exposure` — risk_tier, wildfire/flood/weather factors, triage_priority
- `workshop.cre_risk` — risk_tier, acquisition_screen_flag, exposure_magnitude_index
- `workshop.capital_markets_signals` — disruption_signal, supply_chain_vulnerability (no risk_tier)
- `workshop.energy_asset_risk` — risk_tier, outage_probability, wildfire_ignition_risk

## MCP Servers

- **Felt**: `https://felt.com/mcp` — Primary for map operations
- **Wherobots**: `https://api.cloud.wherobots.com/mcp/` — Part 1 data engineering
