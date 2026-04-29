# Workshop Seed Data

This folder contains scripts and CSV exports used to seed the Aurora PostgreSQL
instance for the AWS Geospatial Workshop.

## Default path: CloudFormation auto-seed

When you deploy `infrastructure/cloudformation.yaml`, a Lambda-backed custom
resource (`AuroraSeed`) automatically:

1. Enables `postgis`, `postgis_raster`, and `aws_s3` extensions
2. Creates the `workshop` schema and `workshop.insurance_exposure` table
3. Bulk-loads `workshop.insurance_exposure` from a public S3 object via
   `aws_s3.table_import_from_s3` (the file is `Content-Encoding: gzip`,
   so Aurora streams + decompresses it server-side)

Default seed source:
`s3://aws-felt-wherobots-workshop-755035179626/seed/insurance_exposure.csv.gz`

To refresh that file from a populated source DB, set `AURORA_DSN` and run
`./scripts/upload_seed_to_s3.sh` — it dumps the table, gzips it, and reuploads
with the right metadata. Bump `SeedVersion` on a CFN update to re-trigger the
import (or set `--parameter-overrides SeedDataKey=...` to point at a new key).

The remaining gold tables (`cre_risk`, `capital_markets_signals`,
`energy_asset_risk`) are still produced by Part 1's Wherobots pipeline.

## Manual path: scripts in this folder

The `export_gold_tables.py` / `import_tables.py` pair is for local dev when
you want to reseed an Aurora cluster outside CloudFormation (or seed all four
gold tables, not just `insurance_exposure`).

## Tables

| Table | Description |
|---|---|
| `workshop.scoring_config` | Per-industry factor weights and scoring methodology |
| `workshop.insurance_exposure` | Insurance portfolio exposure with wildfire/flood/weather risk |
| `workshop.cre_risk` | Commercial real-estate parcels enriched with risk scores |
| `workshop.capital_markets_signals` | Capital-markets signals (disruption, supply chain) |
| `workshop.energy_asset_risk` | Energy infrastructure assets with composite hazard risk |

## Export (from an existing Aurora instance)

Use this when you have a populated database and want to create seed CSVs.

```bash
pip install psycopg2-binary python-dotenv
python data/seed/export_gold_tables.py
```

This writes CSV files and a `create_tables.sql` DDL file into this directory.
Geometry columns are exported as WKT text.

## Import (into a fresh Aurora instance)

Use this to populate a new Aurora cluster from the seed CSVs.

1. **Place CSVs** in `data/seed/csv/` — one file per table:
   - `insurance_exposure.csv`
   - `cre_risk.csv`
   - `capital_markets_signals.csv`
   - `energy_asset_risk.csv`
   - `scoring_config.csv` (optional)

2. **Set `AURORA_DSN`** in `.env` at the project root.

3. **Run the import:**

   ```bash
   pip install psycopg2-binary python-dotenv
   python data/seed/import_tables.py
   ```

The import script will:
- Create the `workshop` schema and all tables (from `aurora_schema.sql`)
- Enable the PostGIS extension
- Load each CSV using PostgreSQL `COPY` (fast bulk load)
- Convert WKT geometry strings back to PostGIS geometry columns
- Truncate tables before loading (safe to re-run)

## File Layout

```
data/seed/
├── README.md                  ← this file
├── export_gold_tables.py      ← export script (DB → CSV)
├── import_tables.py           ← import script (CSV → DB)
└── csv/
    ├── .gitkeep
    ├── insurance_exposure.csv  ← (after export)
    ├── cre_risk.csv
    ├── capital_markets_signals.csv
    └── energy_asset_risk.csv
```
