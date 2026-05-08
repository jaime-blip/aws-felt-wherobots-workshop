# Setting Up Wherobots in Kiro

This guide covers installing the Wherobots extension in Kiro, connecting to the MCP server for spatial Q&A, and attaching a remote Wherobots runtime for notebook execution.

**Requirements:**
- [Kiro IDE](https://kiro.dev) installed
- Wherobots account (Professional or Enterprise Organization Edition)
- Wherobots API key (Console → API Keys)
- GitHub Copilot subscription (for AI-assisted features)

---

## 1. Install the Wherobots Extension

From the terminal:

```bash
kiro --install-extension wherobots.wherobotsjobsubmit
```

Or install from the [Open VSX Registry](https://open-vsx.org/extension/Wherobots/wherobotsjobsubmit) directly in Kiro's extensions panel.

After installing, pin the Wherobots icon to your sidebar for quick access.

## 2. Set Your API Key

1. Open Command Palette: **Cmd+Shift+P** (macOS) / **Ctrl+Shift+P** (Linux/Windows)
2. Select **Wherobots: Set API Key**
3. Paste your API key — it's stored in Kiro's Secret Storage

If you don't have a key yet, select **Wherobots: Generate API Key on Wherobots Cloud** instead.

## 3. Configure the MCP Server

The extension auto-configures the Wherobots MCP server when you set your API key. If you need to configure it manually (or for use with Claude Code / other tools), add this to your MCP config:

```json
{
  "mcpServers": {
    "wherobots": {
      "url": "https://api.cloud.wherobots.com/mcp/",
      "type": "http",
      "headers": {
        "x-api-key": "<YOUR_WHEROBOTS_API_KEY>"
      }
    }
  }
}
```

**Verify the connection:**
1. Open the AI assistant chat (View → Chat)
2. Switch to **Agent** mode
3. Ask: *"Show me the catalogs in my Organization"*
4. You should see the MCP call `list_catalogs` and get back catalog names

The MCP server runs in `us-west-2`. It supports catalog exploration, spatial SQL generation, and query execution — all through natural language.

## 4. Connect a Notebook to Wherobots Compute

This is how you run the Part 1 medallion pipeline notebooks against real Wherobots Cloud infrastructure.

### Create a Workspace

1. Open the **Wherobots** panel in the sidebar
2. Click **Create Workspace**
3. Configure:
   - **Region**: `us-west-2` (or your preferred region)
   - **Instance Size**: Choose based on workload. For this workshop's reference notebooks:
     - `bronze-to-silver.ipynb` → **Medium** (raster zonal stats + spatial KNN benefit from extra memory)
     - `silver-to-gold.ipynb` → **Small** (SQL-only on pre-joined Silver tables — no spatial joins or rasters)
4. Click **Start** — this provisions a remote Sedona runtime

### Connect Your Notebook

1. Open a `.ipynb` file (e.g., `part1_data_engineering/bronze-to-silver.ipynb`)
2. In the notebook kernel picker, select the Wherobots remote runtime
3. Code now executes on Wherobots Cloud — Sedona SQL, raster operations, spatial joins all run on the provisioned cluster

### Monitor and Manage

From the Wherobots sidebar you can:
- View workspace status
- Open the **Spark UI** to monitor jobs
- Open the **Wherobots Console** for full management
- **Stop the workspace** when done — this tears down the runtime and stops billing

### Settings Reference

| Setting | Purpose | Default |
|---|---|---|
| `region` | Cloud region for workspaces | — |
| `instanceSize` | Runtime size | — |
| `timeout` | Job timeout (seconds) | — |
| `mcpServerRuntimeId` | Runtime ID for MCP queries | — |
| `mcpServerRuntimeRegion` | Runtime region for MCP | — |

Access all settings via Command Palette → **Wherobots: Open Settings**.

## 5. Browse the Data Hub

The extension sidebar includes a **Data Hub** browser. Use it to:
- Browse all catalogs, schemas, and tables in your Organization
- Preview table schemas without writing SQL
- Navigate `wherobots_open_data` (community data) and `org_catalog` (your org's data)

For this workshop, the key tables are:

| Dataset | Table Path |
|---|---|
| Overture Buildings | `wherobots_open_data.overture_maps_foundation.buildings_building` |
| USFS Burn Probability | `org_catalog.wildfire_risk.burn_probability_conus` |
| OPERA DSWx-S1 | `org_catalog.opera.dswx_s1` |
| NOAA Severe Weather | `org_catalog.noaa_swdi.hail` / `structure` / `tvs` |

---

## Troubleshooting

| Issue | Fix |
|---|---|
| MCP server not responding | Command Palette → MCP: List Servers → select wherobots → Start Server |
| Extension commands not showing | Reload Kiro window (Cmd+Shift+P → "Reload Window") |
| Workspace won't start | Check API key is set, verify account has Professional/Enterprise tier |
| Notebook can't find kernel | Ensure workspace is running, then re-select kernel |

## Claude Code Alternative

If you prefer using Claude Code instead of the Kiro AI assistant:

```bash
claude mcp add --transport http wherobots https://api.cloud.wherobots.com/mcp/ \
  --scope user --header "X-API-Key: <YOUR_WHEROBOTS_API_KEY>"
```

This gives Claude Code the same MCP catalog browsing and spatial SQL capabilities.
