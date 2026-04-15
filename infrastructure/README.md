# Infrastructure — CloudFormation Deployment

This CloudFormation template provisions all AWS resources needed for the Geospatial Workshop.

## What It Creates

| Resource | Details |
|---|---|
| **VPC** | 10.0.0.0/16 with 2 public + 2 private subnets across 2 AZs |
| **Aurora PostgreSQL Serverless v2** | Engine 16.4, 0.5–8 ACU, public subnets, encrypted, publicly accessible |
| **Security Groups** | Aurora inbound on 5432 (open for workshop; restrict in production) |
| **IAM Role** | Bedrock `InvokeModel` for Claude and Nova models |

## Prerequisites

- AWS CLI configured with appropriate permissions
- An AWS account with Bedrock model access enabled in your target region

## Deploy

```bash
aws cloudformation deploy \
  --template-file infrastructure/cloudformation.yaml \
  --stack-name geospatial-workshop \
  --parameter-overrides \
      DBMasterUsername=workshop_admin \
      DBMasterPassword='YourSecurePassword123!' \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2
```

## Post-Deploy Setup

1. **Get outputs:**

   ```bash
   aws cloudformation describe-stacks \
     --stack-name geospatial-workshop \
     --query 'Stacks[0].Outputs' \
     --output table
   ```

2. **Connect directly to Aurora from your machine:**

   ```bash
   psql "postgresql://workshop_admin:<PASSWORD>@<AuroraEndpoint>:5432/workshop"
   ```

3. **Enable PostGIS on Aurora:**

   ```sql
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE SCHEMA IF NOT EXISTS workshop;
   ```

4. **Seed the database** — see `data/seed/README.md` for import instructions, or run:

   ```bash
   python3 data/seed/import_tables.py
   ```

5. **Update `.env`** with the Aurora DSN from the stack outputs:

   ```
   AURORA_DSN=postgresql://workshop_admin:<PASSWORD>@<AuroraEndpoint>:5432/workshop
   ```

## Tear Down

```bash
aws cloudformation delete-stack --stack-name geospatial-workshop --region us-west-2
```
