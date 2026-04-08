# Workshop Repo Test Prompt

Use this prompt to systematically validate that the repo is deployable from scratch — as if you were Rajesh testing it cold.

---

## Pre-flight: Repo structure check

```bash
cd /Users/strabo/Projects/aws-geospatial-workshop

# 1. Verify all expected files exist
echo "=== Issue 1: Infrastructure ==="
ls infrastructure/cloudformation.yaml infrastructure/README.md

echo "=== Issue 2: Schema consistency ==="
# aurora_schema.sql should use 'workshop' schema, NOT 'gold'
grep -c "gold\." part1_data_engineering/aurora_schema.sql  # Should be 0
grep -c "workshop\." part1_data_engineering/aurora_schema.sql  # Should be >0
# agent.py should reference 'workshop' schema
grep "workshop\." part2_map_agent/agent.py | head -5

echo "=== Issue 3: Data seeding ==="
ls data/seed/import_tables.py data/seed/export_gold_tables.py data/seed/csv/.gitkeep

echo "=== Issue 4: MCP config ==="
ls .kiro/mcp.json

echo "=== Issue 5: Env example ==="
grep "BEDROCK_MODEL_ID" .env.example  # Should exist with a default value

echo "=== Issue 6: Felt connection guide ==="
ls docs/felt-aurora-connection.md
# Also verify it's in the workshop step-by-step
grep -c "Connect Felt to Aurora" workshop-step-by-step.md  # Should be >0
```

## Test 1: CloudFormation template validation

```bash
# Validate the template syntax (requires AWS CLI)
aws cloudformation validate-template \
  --template-body file://infrastructure/cloudformation.yaml \
  --region us-west-2

# Check it has the required resources
grep -E "AWS::RDS|AWS::EC2|AWS::IAM|AWS::Bedrock" infrastructure/cloudformation.yaml
```

**Expected:** Template validates. Contains Aurora, EC2 (bastion), VPC, IAM, security group resources.

## Test 2: Schema consistency audit

```bash
# No 'gold.' references in agent code or workshop docs (except Wherobots Iceberg paths)
echo "--- agent.py gold refs (should be 0) ---"
grep -n "gold\." part2_map_agent/agent.py | grep -v "org_catalog"

echo "--- workshop step-by-step gold refs (should be 0) ---"
grep -n "gold\." workshop-step-by-step.md | grep -v "Gold" | grep -v "gold layer" | grep -v "Silver → Gold"

echo "--- aurora_schema.sql uses workshop (should be >0) ---"
grep "CREATE SCHEMA" part1_data_engineering/aurora_schema.sql

echo "--- data_dictionary references (should be workshop) ---"
grep -i "aurora.*workshop\|workshop.*table" part1_data_engineering/data_dictionary.md | head -3
```

**Expected:** All table references use `workshop.*`. The only `gold.` references should be Wherobots Iceberg catalog paths (`org_catalog.gold.*`).

## Test 3: Import script syntax check

```bash
cd data/seed
python3 -c "import ast; ast.parse(open('import_tables.py').read()); print('OK')"
python3 -c "import ast; ast.parse(open('export_gold_tables.py').read()); print('OK')"
```

**Expected:** Both scripts parse without syntax errors.

## Test 4: MCP config is valid JSON

```bash
python3 -c "import json; json.load(open('.kiro/mcp.json')); print('OK')"
```

**Expected:** Valid JSON.

## Test 5: .env.example completeness

```bash
echo "=== Required vars ==="
for var in WHEROBOTS_API_KEY AURORA_DSN FELT_API_TOKEN FELT_SOURCE_ID AWS_PROFILE AWS_DEFAULT_REGION BEDROCK_MODEL_ID; do
  grep -q "$var" .env.example && echo "✅ $var" || echo "❌ $var MISSING"
done
```

**Expected:** All 7 vars present.

## Test 6: Workshop step-by-step has Felt connection step

```bash
# Should be Step 4 in Setup
grep -A 2 "Step 4.*Connect Felt" workshop-step-by-step.md
# Should reference network considerations
grep "felt-aurora-connection.md" workshop-step-by-step.md
```

**Expected:** Step 4 covers Felt-to-Aurora connection. Links to full guide for network details.

## Test 7: Full deployment test (requires AWS account + credentials)

```bash
# Deploy CloudFormation
aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yaml \
  --stack-name geospatial-workshop-test \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides MasterUsername=workshop_admin MasterUserPassword=<password> \
  --region us-west-2

# Get outputs
aws cloudformation describe-stacks \
  --stack-name geospatial-workshop-test \
  --query "Stacks[0].Outputs" --output table

# Connect to Aurora via bastion (SSM)
BASTION_ID=$(aws cloudformation describe-stacks \
  --stack-name geospatial-workshop-test \
  --query "Stacks[0].Outputs[?OutputKey=='BastionInstanceId'].OutputValue" \
  --output text)

aws ssm start-session --target $BASTION_ID

# From bastion, seed data
AURORA_DSN=postgresql://workshop_admin:<password>@<aurora-endpoint>:5432/workshop
python3 data/seed/import_tables.py

# Run verification from workshop step-by-step Step 5
python3 -c "
import psycopg2, os
conn = psycopg2.connect('$AURORA_DSN')
cur = conn.cursor()
for table in ['insurance_exposure', 'cre_risk', 'capmarkets_signals', 'energy_infra_risk']:
    cur.execute(f'SELECT COUNT(*) FROM workshop.{table}')
    print(f'workshop.{table}: {cur.fetchone()[0]:,} rows')
conn.close()
"

# Run the agent
cd part2_map_agent
./run.sh "Show me buildings with elevated insurance risk in San Diego"

# Cleanup
aws cloudformation delete-stack --stack-name geospatial-workshop-test
```

**Expected:** Full stack deploys, data seeds, agent creates a Felt map.

---

## Quick smoke test (no AWS needed)

Run Tests 1-6 above. They validate repo structure, schema consistency, and file correctness without needing AWS credentials or a live Aurora instance.

```bash
cd /Users/strabo/Projects/aws-geospatial-workshop
echo "=== SMOKE TEST ==="
# Files exist
test -f infrastructure/cloudformation.yaml && echo "✅ CloudFormation" || echo "❌ CloudFormation"
test -f data/seed/import_tables.py && echo "✅ Import script" || echo "❌ Import script"
test -f .kiro/mcp.json && echo "✅ MCP config" || echo "❌ MCP config"
test -f docs/felt-aurora-connection.md && echo "✅ Felt guide" || echo "❌ Felt guide"

# Schema check
test $(grep -c "gold\." part1_data_engineering/aurora_schema.sql) -eq 0 && echo "✅ No gold.* in schema SQL" || echo "❌ gold.* still in schema SQL"
test $(grep -c "workshop\." part1_data_engineering/aurora_schema.sql) -gt 0 && echo "✅ workshop.* in schema SQL" || echo "❌ No workshop.* in schema SQL"

# Env completeness
grep -q "BEDROCK_MODEL_ID" .env.example && echo "✅ BEDROCK_MODEL_ID in .env.example" || echo "❌ BEDROCK_MODEL_ID missing"

# Workshop has Felt step
grep -q "Connect Felt to Aurora" workshop-step-by-step.md && echo "✅ Felt step in workshop" || echo "❌ Felt step missing from workshop"

# Python syntax
python3 -c "import ast; ast.parse(open('data/seed/import_tables.py').read())" 2>/dev/null && echo "✅ import_tables.py valid" || echo "❌ import_tables.py syntax error"

# JSON valid
python3 -c "import json; json.load(open('.kiro/mcp.json'))" 2>/dev/null && echo "✅ mcp.json valid" || echo "❌ mcp.json invalid"

echo "=== DONE ==="
```
