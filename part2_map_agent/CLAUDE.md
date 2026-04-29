# Part 2 — Map Builder AI Agent

See the root `CLAUDE.md` for the full project overview.

## Quick Reference

- **Agent**: `agent.py` — Strands Agent (Bedrock Claude Sonnet) with python_repl + file_read + AgentSkills
- **Skills**: `skills/aurora-postgis/` and `skills/felt-mapping/`
- **Evals**: `evals/` — LLM-as-judge framework for testing skill quality
- **Run**: `./run.sh "your prompt"` or `./run.sh` for interactive mode

## Architecture

```
User prompt → Strands Agent → reads skills/*.md → generates Python →
  python_repl executes: psycopg2 → Aurora, felt_python → Map, FSL → Styling →
  returns Felt map URL
```

## Data (pre-loaded in Aurora, `workshop` schema)

4 Gold tables, ~1M San Diego buildings each:
- `workshop.insurance_exposure` — risk_tier, wildfire/flood/weather factors, triage_priority, relative_risk_band
- `workshop.cre_risk` — risk_tier, acquisition_screen_flag, exposure_magnitude_index
- `workshop.capital_markets_signals` — disruption_signal, supply_chain_vulnerability, event_density_signal (no risk_tier)
- `workshop.energy_asset_risk` — risk_tier, outage_probability, wildfire_ignition_risk

## MCP Servers

- **Wherobots**: `https://api.cloud.wherobots.com/mcp/`
- **Felt**: `https://felt.com/mcp`
