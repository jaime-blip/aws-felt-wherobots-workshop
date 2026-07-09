#!/usr/bin/env python3
"""
Map Builder Agent
==================

A Strands agent that builds Felt maps from Aurora PostgreSQL data using the Felt MCP.

Architecture:
  - Primary: Felt MCP tools (create_map, create_layer_from_data_source, generate_fsl, etc.)
  - Fallback: python_repl (psycopg2 for Aurora, felt-python for uploads)
  - Skills: aurora-postgis (fallback), felt-mapping (MCP tool docs)

Usage:
    python agent.py "Map wildfire locations colored by cause"
    python agent.py  # interactive mode
"""

import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env", override=True)

# Configure python_repl: auto-approve, non-interactive, keep state
os.environ.setdefault("BYPASS_TOOL_CONSENT", "true")
os.environ.setdefault("PYTHON_REPL_INTERACTIVE", "false")
os.environ.setdefault("PYTHON_REPL_RESET_STATE", "false")

from mcp.client.streamable_http import streamablehttp_client
from strands import Agent, AgentSkills
from strands.tools.mcp import MCPClient
from strands.tools.mcp.mcp_client import CLIENT_SESSION_NOT_RUNNING_ERROR_MESSAGE
from strands.types.exceptions import MCPClientInitializationError
from strands_tools import file_read, python_repl

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────
SKILLS_DIR = Path(__file__).parent / "skills"

# Felt's MCP runs each tool call as an HTTP request. A heavy data-source query
# (e.g. a spatial filter over ~1M buildings) makes the synchronous validation
# step run long; the default 30s HTTP timeout aborts it. Bump it. The actual
# layer processing is async and handled via poll_layer_processing_status, so
# these only need to cover the request/response round-trip.
FELT_MCP_TIMEOUT = float(os.environ.get("FELT_MCP_TIMEOUT", "120"))
FELT_MCP_SSE_READ_TIMEOUT = float(os.environ.get("FELT_MCP_SSE_READ_TIMEOUT", "600"))
# How many times to rebuild the session and retry a tool call after a drop.
FELT_MCP_MAX_RETRIES = int(os.environ.get("FELT_MCP_MAX_RETRIES", "1"))

# Name of the Felt data source connected to Aurora. Must match the source
# created in Setup Step 6 (the Step 6 Option A command names it from this
# same env var, so both sides stay in sync).
FELT_SOURCE_NAME = os.environ.get("FELT_SOURCE_NAME", "").strip() or "workshop-db"

# ── Skills Plugin ──────────────────────────────────────────────
skills_plugin = AgentSkills(skills=str(SKILLS_DIR))


# ── Felt MCP Client ────────────────────────────────────────────
# Read-only / side-effect-free tools that are SAFE to auto-retry after a drop.
# Everything else (create_*, update_*, delete_*, add_*, import_*, upload_*,
# duplicate_*, refresh_*, share_*, upsert_*) is treated as non-idempotent: a
# dropped connection during such a call often means it ALREADY succeeded
# server-side (Felt registers the layer and processes async even when the
# synchronous response times out), so retrying would create a duplicate.
_IDEMPOTENT_TOOL_PREFIXES = (
    "list_", "get_", "browse_", "inspect_", "poll_", "render_", "search_", "generate_",
)
_IDEMPOTENT_TOOL_NAMES = frozenset({"who_am_i"})


class ResilientMCPClient(MCPClient):
    """MCPClient that transparently rebuilds a dropped Felt session.

    Strands runs the MCP connection on a background thread. When the
    streamable-HTTP transport is closed mid-call (Felt-side timeout on a heavy
    query, proxy idle cap, or a network blip), that thread dies and *every*
    later tool call raises "the client session is not running" for the rest of
    the process — there is no built-in reconnect. We detect the dead session
    and rebuild it via stop()+start() (which reset state for reuse). The same
    MCPAgentTool objects keep working because they reference this client, not
    the underlying session.

    Retry is idempotency-aware: read-only tools are retried after a reconnect;
    mutating tools (e.g. create_layer_from_data_source) are NOT retried, because
    a drop during them usually means the work already landed server-side and a
    retry would duplicate it. For those we just reconnect so the next call (the
    model polling / get_map_layers to find the layer) works.
    """

    @staticmethod
    def _is_idempotent(name: str) -> bool:
        short = name.split("__")[-1]  # strip any "server__" prefix
        return short in _IDEMPOTENT_TOOL_NAMES or short.startswith(_IDEMPOTENT_TOOL_PREFIXES)

    def _reconnect(self) -> bool:
        # _reconnect only ever runs on an already-inactive session, so the
        # background thread is dead or mid-teardown and there's nothing to join.
        # Drop the reference unconditionally so stop() skips signaling a
        # close-event onto that dead/dying loop — scheduling onto it leaks an
        # un-awaited coroutine and emits a RuntimeWarning. (Checking is_alive()
        # here is racy: just after a drop the thread is briefly still alive
        # while it unwinds.) stop() still closes the loop and resets state.
        self._background_thread = None
        try:
            self.stop(None, None, None)
        except Exception:
            logger.debug("error during stop() before reconnect", exc_info=True)
        try:
            self.start()
            print("🔄 Felt MCP session reconnected")
            return True
        except Exception:
            logger.exception("failed to reconnect Felt MCP session")
            return False

    async def call_tool_async(self, tool_use_id, name, arguments=None, read_timeout_seconds=None):
        idempotent = self._is_idempotent(name)
        for attempt in range(FELT_MCP_MAX_RETRIES + 1):
            if not self._is_session_active() and not self._reconnect():
                break
            try:
                result = await super().call_tool_async(
                    tool_use_id, name, arguments, read_timeout_seconds
                )
            except MCPClientInitializationError:
                continue  # session died at entry — loop to rebuild and retry
            # Live session ⇒ the call went through. A dead session here means
            # the connection dropped during the call.
            if self._is_session_active():
                return result
            if not idempotent:
                # The call may have already landed server-side; retrying would
                # duplicate it. Reconnect for subsequent calls, then surface the
                # result so the model can poll / get_map_layers to find it.
                print(f"⚠️  Felt MCP dropped during '{name}' — reconnected; not retrying "
                      f"(may have succeeded server-side; check via poll/get_map_layers)")
                self._reconnect()
                return result
            if attempt == FELT_MCP_MAX_RETRIES:
                return result
            print(f"⚠️  Felt MCP dropped during '{name}' — reconnecting and retrying")
        return self._handle_tool_execution_error(
            tool_use_id, MCPClientInitializationError(CLIENT_SESSION_NOT_RUNNING_ERROR_MESSAGE)
        )

    def call_tool_sync(self, tool_use_id, name, arguments=None, read_timeout_seconds=None):
        idempotent = self._is_idempotent(name)
        for attempt in range(FELT_MCP_MAX_RETRIES + 1):
            if not self._is_session_active() and not self._reconnect():
                break
            try:
                result = super().call_tool_sync(
                    tool_use_id, name, arguments, read_timeout_seconds
                )
            except MCPClientInitializationError:
                continue
            if self._is_session_active():
                return result
            if not idempotent:
                print(f"⚠️  Felt MCP dropped during '{name}' — reconnected; not retrying "
                      f"(may have succeeded server-side; check via poll/get_map_layers)")
                self._reconnect()
                return result
            if attempt == FELT_MCP_MAX_RETRIES:
                return result
            print(f"⚠️  Felt MCP dropped during '{name}' — reconnecting and retrying")
        return self._handle_tool_execution_error(
            tool_use_id, MCPClientInitializationError(CLIENT_SESSION_NOT_RUNNING_ERROR_MESSAGE)
        )


felt_mcp_client = ResilientMCPClient(
    lambda: streamablehttp_client(
        url="https://felt.com/mcp",
        headers={"Authorization": f"Bearer {os.environ.get('FELT_API_TOKEN', '')}"},
        timeout=timedelta(seconds=FELT_MCP_TIMEOUT),
        sse_read_timeout=timedelta(seconds=FELT_MCP_SSE_READ_TIMEOUT),
    )
)

# ── Seed python_repl state (fallback only) ─────────────────────
_SEED_CODE = f"""
import os, json, psycopg2
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path("{Path(__file__).parent.parent / '.env'}"), override=True)

# Fallback: felt-python for uploads if MCP fails
from felt_python import upload_file

# Fallback: Aurora direct access
AURORA_DSN = os.environ.get("AURORA_DSN", "")
FELT_TOKEN = os.environ.get("FELT_API_TOKEN", "")

print("✅ Fallback ready: psycopg2, felt-python")
"""

# ── System Prompt ──────────────────────────────────────────────
SYSTEM_PROMPT = """You are a geospatial map builder agent. You create interactive Felt maps from PostgreSQL/PostGIS data using the Felt MCP tools.

## Available Data (workshop schema — 1,035,306 San Diego buildings each)

### workshop.insurance_exposure
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, risk_tier, exposure_delta, triage_priority, relative_risk_band, score_explanation, weather_window_start, weather_window_end

### workshop.cre_risk
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, risk_tier, acquisition_screen_flag (boolean), exposure_magnitude_index, hazard_proximity_m, score_explanation

### workshop.capital_markets_signals
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, disruption_signal, supply_chain_vulnerability, event_density_signal, score_explanation, weather_window_start, weather_window_end

### workshop.energy_asset_risk
Columns: asset_id, geometry, building_class, wildfire_factor, flood_factor, severe_weather_factor, risk_score, risk_tier, outage_probability, wildfire_ignition_risk, weather_impact_frequency, score_explanation

Risk tiers: low, moderate, elevated, high, critical
Region: San Diego County, CA (center: 32.7157, -117.1611)
Note: `capital_markets_signals` has no `risk_tier` column — use `risk_score` thresholds instead.

## Primary Workflow (Felt MCP Tools)

Use these MCP tools in sequence:

1. **list_data_sources** — Find the Aurora data source (look for "__FELT_SOURCE_NAME__" or similar PostgreSQL source)
2. **create_map** — Create a new map with title, center lat/lon, zoom level
3. **create_layer_from_data_source** — Add a layer via SQL query against Aurora
4. **poll_layer_processing_status** — Wait for layer to finish processing (use wait_seconds=30)
5. **generate_fsl** — Generate styling (pass layer_id, geometry_type, description of desired style)
6. **update_layer_properties** — Apply the generated FSL style to the layer
7. **render_map** — Show the map inline (call this LAST after all edits)

### A `create_layer_from_data_source` timeout is usually NOT a failure

For a large layer, the synchronous response to `create_layer_from_data_source`
can exceed the connection timeout and surface as a timeout or "connection
closed" error — but Felt has almost always **already registered the layer** and
is processing it asynchronously. So when a create errors out:

- **Do NOT call `create_layer_from_data_source` again** — a retry creates a
  DUPLICATE layer.
- Instead call **`get_map_layers`** to find the layer that was registered, then
  **`poll_layer_processing_status`** on it until `completed`.
- Only recreate if `get_map_layers` shows the layer genuinely did not register.
- If you ever do find a duplicate, delete the extra one with `delete_layer`.

## Example Tool Sequence

User: "Show elevated risk buildings colored by tier"

1. Call `list_data_sources` → find data_source_id for PostgreSQL source
2. Call `create_map`:
   - title: "Elevated Risk Buildings"
   - latitude: 32.7157
   - longitude: -117.1611
   - zoom: 10
   - basemap: "dark"  (risk maps read best on dark — colors and heat pop)
3. Call `create_layer_from_data_source`:
   - data_source_id: <from step 1>
   - sql_query: "SELECT asset_id, building_class, risk_score, risk_tier, geometry FROM workshop.insurance_exposure WHERE risk_tier = 'elevated'"
   - name: "Elevated Risk"
4. Call `poll_layer_processing_status`:
   - wait_seconds: 30
5. Call `generate_fsl`:
   - layer_id: <from step 3>
   - geometry_type: "polygon"
   - description: "Categorical coloring by risk_tier. Orange for elevated, red for high, dark red for critical."
6. Call `update_layer_properties`:
   - layer_id: <from step 3>
   - style: <FSL from step 5>
7. Call `render_map` — shows inline preview
8. Return the map URL to the user

## Adding Buffer/Reference Layers

To add a buffer circle (e.g., "10 miles from downtown"):

Use `create_layer_from_data_source` with PostGIS ST_Buffer:
```sql
SELECT
    'Downtown 10-mile buffer' as name,
    ST_Buffer(
        ST_SetSRID(ST_MakePoint(-117.1611, 32.7157), 4326)::geography,
        16093.44
    )::geometry as geometry
```

Then style with transparent fill + colored stroke via `generate_fsl`.

## Zoom-Aware & Heatmap Styling

Felt styles can react to zoom. Any numeric paint property accepts a ramp
`{"linear": [[zoom, value], ...]}` (plus `minZoom`/`maxZoom`) — there is no
separate visibility API, so use an `opacity` ramp to fade layers in/out by zoom.

Flagship pattern — **risk-density heatmap that resolves into features**: an H3
hexbin layer (`type: "h3"`, `aggregation: "mean"` of a metric like `risk_score`,
`binMode: "high"` for fine hotspots) on a **dark** basemap, fading OUT as you
zoom in (`opacity {"linear": [[10,0.9],[13,0]]}`), cross-faded with the actual
features fading IN (`{"linear": [[11,0],[13,0.85]]}`). H3 bins by point, so query
`ST_Centroid(geometry)` for the hexbin layer; keep polygons for the detail layer.
See the `felt-mapping` skill ("Pattern: Risk-density heatmap…") for the full recipe.

## SQL Requirements

- ALWAYS use `workshop.` schema prefix (e.g., `workshop.insurance_exposure`)
- ALWAYS include a geometry column in SELECT
- Use LIMIT for large result sets (max 100,000 rows)
- Common spatial functions: ST_DWithin, ST_Intersects, ST_Buffer, ST_MakePoint

### NEVER `SELECT *` — select only the columns the layer needs

`create_layer_from_data_source` makes Felt pull and process the entire result
synchronously before the layer is registered. A wide `SELECT *` over many rows
ships a huge payload and can drop the connection mid-call.

- **List explicit columns**: `geometry` + the fields you actually style or show
  in popups (e.g. `asset_id, building_class, risk_score, risk_tier, geometry`).
- **Never pull large free-text columns into a layer** unless explicitly asked —
  especially `score_explanation` (it is bigger than the geometry itself and the
  map never renders it). The same goes for any other long narrative/text column.
- Selecting fewer columns roughly halves the payload Felt must process and does
  NOT change which features appear on the map — only `LIMIT` changes that, so
  keep all matching rows unless the user asks to cap them.

Example — county-wide risk buildings, trimmed to what the map uses:
```sql
SELECT asset_id, building_class, risk_score, risk_tier, geometry
FROM workshop.insurance_exposure
WHERE risk_tier IN ('elevated', 'high', 'critical')
```

## Fallback (python_repl)

Use python_repl ONLY when:
- MCP upload fails
- Complex data transforms that can't be done in SQL
- Aurora connectivity debugging

```python
import psycopg2
conn = psycopg2.connect(AURORA_DSN)
cur = conn.cursor()
cur.execute("SELECT count(*) FROM workshop.insurance_exposure")
print(cur.fetchone())
conn.close()
```

## Critical Rules

- ALWAYS call `list_data_sources` first to get the data source ID
- ALWAYS call `poll_layer_processing_status` after adding a layer
- ALWAYS call `render_map` as the LAST step (it captures a snapshot)
- ALWAYS include the map URL in your response
- Use `generate_fsl` for styling — don't hand-write FSL
- One map per request unless explicitly asked for multiple
""".replace("__FELT_SOURCE_NAME__", FELT_SOURCE_NAME)


# ── Agent Factory ──────────────────────────────────────────────

def get_model():
    """Get the best available Bedrock model."""
    from strands.models.bedrock import BedrockModel
    return BedrockModel(
        model_id=os.environ.get(
            "BEDROCK_MODEL_ID",
            "us.anthropic.claude-opus-4-8",
        ),
        region_name=(
            os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-west-2"
        ),
    )


def create_agent(felt_tools: list) -> Agent:
    """Create the map builder agent with Felt MCP tools."""
    agent = Agent(
        model=get_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=[python_repl, file_read] + felt_tools,
        plugins=[skills_plugin],
    )

    # Seed python_repl with fallback imports
    agent.tool.python_repl(code=_SEED_CODE)

    return agent


# ── CLI ────────────────────────────────────────────────────────

def _preflight():
    """Fail fast with a clear message if required credentials are missing."""
    token = os.environ.get("FELT_API_TOKEN", "").strip()
    if not token or token == "your-felt-api-token":
        print("❌ FELT_API_TOKEN is not set in your .env.")
        print("   The Map Builder Agent needs a Felt API token to reach the Felt MCP.")
        print("   Get one at Felt → Settings → Integrations (it starts with 'felt_pat_'),")
        print("   set FELT_API_TOKEN=... in the repo-root .env, then re-run ./run.sh.")
        sys.exit(1)
    dsn = os.environ.get("AURORA_DSN", "").strip()
    if not dsn or "your-aurora-host" in dsn:
        print("⚠️  AURORA_DSN looks unset — Felt will connect, but Aurora queries may fail.")
        print("   Set AURORA_DSN in .env (the AuroraDSN from your CloudFormation outputs).\n")


def _check_felt_source():
    """Warn early if the Aurora data source is missing from Felt (Setup Step 6).

    Every Part 2 prompt starts with list_data_sources; if the FELT_SOURCE_NAME
    source was never created, the agent stalls on its very first tool call
    with no hint of why. Non-fatal: skills/instructor setups may differ.
    """
    try:
        result = felt_mcp_client.call_tool_sync(
            tool_use_id="preflight-list-data-sources",
            name="list_data_sources",
            arguments={},
        )
        text = str(result.get("content", "")).lower()
    except Exception:
        return  # non-fatal — the agent surfaces tool errors itself
    if FELT_SOURCE_NAME.lower() not in text and "postgres" not in text:
        print(f"⚠️  No '{FELT_SOURCE_NAME}' (or other Postgres) data source found in Felt —")
        print("    the agent's first step (list_data_sources) will come back empty and")
        print(f"    map prompts will fail. Create the '{FELT_SOURCE_NAME}' source first:")
        print("    Setup Step 6 in workshop-step-by-step.md (one curl command via the")
        print("    Felt API — it names the source from this same FELT_SOURCE_NAME).\n")


def main():
    _preflight()
    print("🗺️  Map Builder Agent (Felt MCP)")
    print("=" * 50)
    print("Build Felt maps from Aurora PostgreSQL data.")
    print("Type 'quit' to exit.\n")
    print("Examples:")
    print('  "Map the high and critical risk buildings, colored by risk tier"')
    print('  "Map wildfire factor as a heat gradient"')
    print('  "Compare insurance vs CRE risk tiers"')
    print()

    # Connect to Felt MCP and stay connected for the session
    try:
        with felt_mcp_client:
            print("🔌 Connecting to Felt MCP...")
            felt_tools = felt_mcp_client.list_tools_sync()
            print(f"✅ Felt MCP connected ({len(felt_tools)} tools available)")
            print()

            _check_felt_source()

            agent = create_agent(felt_tools)

            # Single prompt from CLI args
            if len(sys.argv) > 1:
                prompt = " ".join(sys.argv[1:])
                print(f"🔍 {prompt}\n")
                agent(prompt)
                print()

            # Interactive loop (stays inside MCP context)
            while True:
                try:
                    prompt = input("🔍 > ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n👋 Bye!")
                    break
                if not prompt:
                    continue
                if prompt.lower() in ("quit", "exit", "q"):
                    print("👋 Bye!")
                    break
                print()
                agent(prompt)
                print()
    except MCPClientInitializationError:
        print("\n❌ Could not connect to the Felt MCP server (https://felt.com/mcp).")
        print("   The usual cause is an invalid or expired FELT_API_TOKEN.")
        print("   Check FELT_API_TOKEN in your .env (Felt → Settings → Integrations,")
        print("   it starts with 'felt_pat_'), then re-run ./run.sh.")
        sys.exit(1)


if __name__ == "__main__":
    main()
