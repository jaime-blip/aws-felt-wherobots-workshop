# Connecting Felt to Aurora PostgreSQL

This guide walks you through creating a Felt data source that connects directly
to your Aurora PostgreSQL cluster, enabling the Map Builder Agent to query
workshop tables and create maps via the Felt API.

## Prerequisites

- A deployed Aurora PostgreSQL cluster (see `infrastructure/README.md`)
- Network connectivity from Felt to Aurora (Aurora must be publicly accessible
  **or** you must configure VPC peering / a bastion tunnel — see notes below)
- A Felt account with API access

## Step-by-Step

### 1. Open Felt Source Settings

Navigate to **Felt** → **Workspace Settings** → **Sources** → **Add Source**.

> 📸 *Screenshot: Felt workspace settings page showing the "Sources" tab
> with the "Add Source" button highlighted.*

### 2. Select PostgreSQL

Choose **PostgreSQL** from the list of available source types.

> 📸 *Screenshot: Source type selection modal with "PostgreSQL" highlighted
> among options like Snowflake, BigQuery, Databricks, etc.*

### 3. Enter Connection Details

Fill in the connection form with your Aurora cluster details:

| Field | Value |
|---|---|
| **Host** | Your Aurora writer endpoint (e.g., `geospatial-workshop-aurora.cluster-xxxx.us-west-2.rds.amazonaws.com`) |
| **Port** | `5432` |
| **Database** | `workshop` |
| **Username** | `workshop_admin` (or your configured master username) |
| **Password** | Your Aurora master password |
| **Schema** | `workshop` |

> 📸 *Screenshot: PostgreSQL connection form with fields filled in.
> The host field shows the Aurora endpoint format.*

### 4. Test & Save the Connection

Click **Test Connection**. If successful, you'll see a green check mark.
Then click **Save** to create the source.

> 📸 *Screenshot: Connection test success state with green checkmark
> and the "Save" button enabled.*

### 5. Get the Source ID

After saving, the source appears in your sources list. The **Source ID** is
visible in the URL when you click on the source:

```
https://felt.com/workspace/sources/<SOURCE_ID>
```

You can also find it via the Felt API:

```bash
curl -s -H "Authorization: Bearer $FELT_API_TOKEN" \
  https://felt.com/api/v2/sources | jq '.sources[] | {id, name}'
```

> 📸 *Screenshot: Source detail page with the source ID visible in the
> browser URL bar, highlighted with a red box.*

### 6. Update Your `.env`

Add the source ID to your `.env` file at the project root:

```bash
FELT_SOURCE_ID=<your-source-id-from-step-5>
```

### 7. Verify It Works

Test the connection by running a quick query via the Felt API:

```bash
curl -s -X POST \
  -H "Authorization: Bearer $FELT_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "from": "sql",
    "source_id": "'$FELT_SOURCE_ID'",
    "query": "SELECT COUNT(*) FROM workshop.insurance_exposure"
  }' \
  https://felt.com/api/v2/maps/<any-map-id>/add_source_layer
```

## About the Hardcoded Fallback

In `part2_map_agent/agent.py`, line 38, there is a hardcoded fallback source ID:

```python
SOURCE_ID = os.environ.get("FELT_SOURCE_ID", "rYZY3hxzTJCJnEZP2k1r0B")
```

This fallback (`rYZY3hxzTJCJnEZP2k1r0B`) points to the demo Aurora instance
used during development. **You should replace it** by setting `FELT_SOURCE_ID`
in your `.env` file. The fallback exists only so the demo works out of the box
for the workshop team — it will not work for your Aurora cluster.

## Network Considerations

Felt connects to your database from Felt's infrastructure. Your Aurora cluster
needs to be reachable:

- **Option A (simple):** Make Aurora publicly accessible and add Felt's IP
  ranges to the security group. Contact Felt support for current IP ranges.
- **Option B (secure):** Use an SSH tunnel or bastion as a SOCKS proxy.
  This is more complex but keeps Aurora in private subnets.
- **Option C (workshop):** The workshop CloudFormation template places Aurora
  in private subnets. For the workshop, the Felt team pre-configures the
  source connection. Attendees receive the `FELT_SOURCE_ID` as part of setup.
