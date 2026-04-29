# Connecting Felt to Aurora PostgreSQL

This guide walks you through creating a Felt data source that connects directly
to your Aurora PostgreSQL cluster, enabling the Map Builder Agent to query
workshop tables and create maps via the Felt API.

## Prerequisites

- A deployed Aurora PostgreSQL cluster (see `infrastructure/README.md`)
- Aurora must be publicly accessible (the workshop CloudFormation template
  configures this by default)
- A Felt account with API access

## Step-by-Step

### 1. Open a Map in Felt

Open any existing **Map** in Felt, or create a new one. Data sources are
created from within a map, not from workspace settings.

### 2. Add a New Data Source

Click **"Add to map"** (the **+** button in the layer panel), then select
**"Connect a source"** or **"New data source"**.

### 3. Select PostgreSQL

Choose **PostgreSQL** from the list of available source types (alongside
Snowflake, BigQuery, Databricks, etc.).

### 4. Enter Connection Details

Fill in the connection form with your Aurora cluster details:

| Field | Value |
|---|---|
| **Host** | Your Aurora writer endpoint (e.g., `geospatial-workshop-aurora.cluster-xxxx.us-west-2.rds.amazonaws.com`) |
| **Port** | `5432` |
| **Database** | `workshop` |
| **Username** | `workshop_admin` (or your configured master username) |
| **Password** | Your Aurora master password |
| **Schema** | `workshop` |

### 5. Test & Save the Connection

Click **Test Connection**. If successful, you'll see a green check mark.
Then click **Save** to create the source.

The source is now available across your entire workspace — you can use it
from any map.

### 6. Get the Source ID

After saving, retrieve the Source ID via the Felt API:

```bash
curl -s -H "Authorization: Bearer $FELT_API_TOKEN" \
  https://felt.com/api/v2/sources | jq '.sources[] | {id, name}'
```

### 7. Name the Source `workshop-db`

Name the Felt source exactly `workshop-db` when creating it. The agent
resolves the source id by this name at startup — no source id needs to be
saved in `.env`.

If you prefer a different name, set it in `.env`:

```bash
FELT_SOURCE_NAME=my-custom-name
```

### 8. Verify It Works

Run the agent:

```bash
cd part2_map_agent && ./run.sh
```

On startup it prints `✅ Felt source 'workshop-db' → <source_id>`. If the
source isn't found, you'll see a clear error listing the available source
names — rename your source or update `FELT_SOURCE_NAME` to match.

## Source Resolution

`part2_map_agent/agent.py` calls `resolve_source_id()` from
`felt_helpers.py`, which queries Felt's `list_sources` API and matches by
name (case-insensitive). This replaces the previous `FELT_SOURCE_ID` env
var. If you had one set, you can delete it.

## Network Considerations

Felt connects to your database from Felt's infrastructure. Your Aurora cluster
needs to be reachable:

- **Workshop setup (default):** Aurora is publicly accessible with the security
  group allowing inbound on port 5432. This works out of the box for the
  workshop. In production, restrict the security group to Felt's IP ranges
  (contact Felt support for current ranges) or your corporate CIDR.
- **Production option:** Use VPC peering or AWS PrivateLink for private
  connectivity between Felt and your Aurora cluster.
