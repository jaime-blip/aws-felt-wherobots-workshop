# Gold Table Seed Data

This folder contains scripts and CSV exports used to seed the Aurora PostgreSQL
instance provisioned by CloudFormation for the AWS Geospatial Workshop.

The AWS team (Damion / Sarab) will use these CSV exports to populate the
workshop Aurora instance so that attendees start with pre-computed gold tables.

## Gold tables

| Table | Description |
|---|---|
| `workshop.insurance_exposure` | Insurance portfolio exposure joined with wildfire burn-probability zones |
| `workshop.cre_risk` | Commercial real-estate parcels enriched with flood and fire risk scores |
| `workshop.capmarkets_signals` | Capital-markets signals aggregated to H3 hexagons |
| `workshop.energy_infra_risk` | Energy infrastructure assets with composite hazard risk |

## Usage

1. Copy `.env.example` to `.env` at the project root and fill in `AURORA_DSN`.
2. Run the export script:

   ```bash
   pip install psycopg2-binary python-dotenv
   python data/seed/export_gold_tables.py
   ```

3. The script writes four CSV files and a `create_tables.sql` DDL file into
   this directory. Geometry columns are exported as WKT so they can be
   re-imported with `ST_GeomFromText`.
