#!/usr/bin/env bash
# Dumps workshop.insurance_exposure from AURORA_DSN to a gzipped CSV and
# uploads it to the workshop's public S3 seed prefix. Used to refresh the
# seed file that the CloudFormation Aurora seed Lambda imports at stack
# create/update time.
#
# Usage:
#   AURORA_DSN=postgresql://... ./scripts/upload_seed_to_s3.sh
#
# The destination defaults match infrastructure/cloudformation.yaml's
# SeedDataBucket / SeedDataKey parameters.

set -euo pipefail

BUCKET="${SEED_BUCKET:-aws-felt-wherobots-workshop-755035179626}"
KEY="${SEED_KEY:-seed/insurance_exposure.csv.gz}"
LOCAL="${LOCAL_FILE:-data/insurance_exposure.csv.gz}"

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -z "${AURORA_DSN:-}" ]]; then
  set -a; source .env 2>/dev/null || true; set +a
fi
: "${AURORA_DSN:?AURORA_DSN must be set (in env or .env)}"

mkdir -p "$(dirname "$LOCAL")"

echo "→ Dumping workshop.insurance_exposure → $LOCAL"
python3 - <<PY
import os, gzip, psycopg2
conn = psycopg2.connect(os.environ['AURORA_DSN'])
cur = conn.cursor()
sql = """
COPY (
  SELECT asset_id, geometry::text AS geometry, building_class,
         wildfire_factor, flood_factor, severe_weather_factor,
         risk_score, risk_tier, exposure_delta, triage_priority,
         relative_risk_band, score_explanation::text,
         weather_window_start, weather_window_end, computed_at
  FROM workshop.insurance_exposure
) TO STDOUT WITH (FORMAT csv, HEADER)
"""
with gzip.open("$LOCAL", "wb", compresslevel=9) as f:
    cur.copy_expert(sql, f)
print(f"  {os.path.getsize('$LOCAL')/1024/1024:.1f} MB")
PY

echo "→ Uploading to s3://$BUCKET/$KEY (Content-Encoding: gzip)"
aws s3 cp "$LOCAL" "s3://$BUCKET/$KEY" \
  --content-type "text/csv" \
  --content-encoding "gzip"

echo "✅ Done. Public URL:"
echo "   https://$BUCKET.s3.amazonaws.com/$KEY"
