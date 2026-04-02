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

4 Gold tables, ~358K San Diego buildings each:
- `workshop.insurance_exposure` — risk_tier, wildfire/flood/weather factors, triage_priority
- `workshop.cre_risk` — acquisition_screen_flag, environmental_risk_index
- `workshop.capmarkets_signals` — disruption_probability, supply_chain_vulnerability
- `workshop.energy_infra_risk` — outage_probability, vegetation_encroachment_risk

## MCP Servers

- **Wherobots**: `https://api.cloud.wherobots.com/mcp/`
- **Felt**: `https://felt.com/mcp`
