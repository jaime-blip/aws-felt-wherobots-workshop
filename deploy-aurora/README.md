# Deploy Aurora — CloudFormation

This CloudFormation template provisions the AWS resources the workshop runs
on: an Aurora PostgreSQL cluster (auto-seeded with `workshop.insurance_exposure`),
the VPC it lives in, and the IAM role Part 2's agent uses to call Bedrock.

## What It Creates

| Resource | Details |
|---|---|
| **VPC** | 10.0.0.0/16 with 2 public + 2 private subnets across 2 AZs |
| **Aurora PostgreSQL Serverless v2** | Engine 16.4, 0.5–8 ACU, public subnets, encrypted, publicly accessible |
| **Security Groups** | Aurora inbound on 5432 (open for workshop; restrict in production) |
| **IAM Role** | Bedrock `InvokeModel` + `Converse` (Strands SDK uses the Converse API) for Claude and Nova models |

> **AWS Workshop Studio note:** when this workshop runs on Workshop Studio
> accounts, the participant role (`WSParticipantRole`) must also allow
> `bedrock:Converse` and `bedrock:ConverseStream` — the Strands SDK calls the
> Converse API, so `bedrock:InvokeModel*` alone makes Part 2's agent crash on
> launch with an `AccessDeniedException`. Add these actions to the Workshop
> Studio IAM policy alongside the invoke permissions.

## Prerequisites

- AWS CLI configured with appropriate permissions
- An AWS account with Bedrock model access enabled in your target region

## Deploy

```bash
aws cloudformation deploy \
  --template-file deploy-aurora/cloudformation.yaml \
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

3. **PostGIS + seed data — already done by CloudFormation.**
   The stack's `AuroraSeed` Lambda enables the `postgis`, `postgis_raster`, and
   `aws_s3` extensions, creates the `workshop` schema, and bulk-loads
   `workshop.insurance_exposure` from a public S3 object. Bump `SeedVersion`
   on a stack update to re-run it. To refresh the S3 seed file from a populated
   source DB, run `scripts/upload_seed_to_s3.sh`.

4. **Update `.env`** with the Aurora DSN from the stack outputs:

   ```
   AURORA_DSN=postgresql://workshop_admin:<PASSWORD>@<AuroraEndpoint>:5432/workshop
   ```

## Tear Down

```bash
aws cloudformation delete-stack --stack-name geospatial-workshop --region us-west-2
```
