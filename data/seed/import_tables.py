#!/usr/bin/env python3
"""Import seed CSV files into Aurora PostgreSQL for the workshop.

Reads AURORA_DSN from the project-root .env file, creates the workshop schema
and tables (using aurora_schema.sql), then loads each CSV via psycopg2
COPY. Geometry columns stored as WKT are converted to PostGIS geometries
during a post-load UPDATE step.

Requirements:
    pip install psycopg2-binary python-dotenv

Usage:
    1. Place CSV exports in data/seed/csv/ (one per table).
       Files must be named: <table_name>.csv
       (e.g., insurance_exposure.csv, cre_risk.csv)
    2. Ensure AURORA_DSN is set in .env at the project root.
    3. Run:  python data/seed/import_tables.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = Path(__file__).resolve().parent
CSV_DIR = SEED_DIR / "csv"
SCHEMA_SQL = PROJECT_ROOT / "part1_data_engineering" / "aurora_schema.sql"

SCHEMA_NAME = "workshop"

# Tables to import — order matters if there are FK dependencies (there aren't).
TABLES: list[str] = [
    "scoring_config",
    "insurance_exposure",
    "cre_risk",
    "capital_markets_signals",
    "energy_asset_risk",
]

# Columns that contain WKT geometry and their SRID
GEOMETRY_COLUMNS: dict[str, dict[str, int]] = {
    "insurance_exposure": {"geometry": 4326},
    "cre_risk": {"geometry": 4326},
    "capital_markets_signals": {"geometry": 4326},
    "energy_asset_risk": {"geometry": 4326},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _connect() -> psycopg2.extensions.connection:
    """Return a psycopg2 connection using AURORA_DSN from .env."""
    load_dotenv(PROJECT_ROOT / ".env")
    dsn = os.getenv("AURORA_DSN")
    if not dsn:
        sys.exit("ERROR: AURORA_DSN is not set. Check your .env file at the project root.")
    conn = psycopg2.connect(dsn)
    conn.autocommit = False
    return conn


def _run_schema_sql(conn: psycopg2.extensions.connection) -> None:
    """Execute the DDL from aurora_schema.sql to create schema + tables."""
    if not SCHEMA_SQL.exists():
        sys.exit(f"ERROR: Schema file not found at {SCHEMA_SQL}")

    ddl = SCHEMA_SQL.read_text()
    with conn.cursor() as cur:
        # Enable PostGIS first
        cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
        cur.execute(ddl)
    conn.commit()
    print(f"✅ Schema and tables created from {SCHEMA_SQL.name}")


def _import_csv(
    conn: psycopg2.extensions.connection,
    table: str,
    csv_path: Path,
) -> int:
    """Load a CSV into workshop.<table> using COPY. Returns row count."""
    qualified = f"{SCHEMA_NAME}.{table}"

    # Read header to get column list
    with open(csv_path) as f:
        header_line = f.readline().strip()
    columns = [c.strip().strip('"') for c in header_line.split(",")]
    col_list = ", ".join(f'"{c}"' for c in columns)

    # For tables with geometry columns, import geometry as text first,
    # then convert in a post-step.
    geom_cols = GEOMETRY_COLUMNS.get(table, {})
    if geom_cols:
        # Temporarily alter geometry columns to TEXT for COPY
        with conn.cursor() as cur:
            for gcol in geom_cols:
                cur.execute(
                    f'ALTER TABLE {qualified} ALTER COLUMN "{gcol}" TYPE TEXT;'
                )
        conn.commit()

    # Truncate to allow re-runs
    with conn.cursor() as cur:
        cur.execute(f"TRUNCATE TABLE {qualified};")
    conn.commit()

    # COPY from CSV
    copy_sql = f'COPY {qualified} ({col_list}) FROM STDIN WITH (FORMAT csv, HEADER true)'
    with open(csv_path, "r") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)
    conn.commit()

    # Convert WKT text back to geometry
    if geom_cols:
        with conn.cursor() as cur:
            for gcol, srid in geom_cols.items():
                cur.execute(
                    f'ALTER TABLE {qualified} '
                    f'ALTER COLUMN "{gcol}" TYPE geometry '
                    f'USING ST_GeomFromText("{gcol}", {srid});'
                )
        conn.commit()

    # Row count
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {qualified};")
        count = cur.fetchone()[0]

    return count


def _human_size(nbytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024  # type: ignore[assignment]
    return f"{nbytes:.1f} TB"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if not CSV_DIR.exists():
        sys.exit(f"ERROR: CSV directory not found at {CSV_DIR}\n"
                 f"Export seed data first: python data/seed/export_gold_tables.py")

    conn = _connect()
    print("Connected to Aurora PostgreSQL.\n")

    # Create schema + tables
    _run_schema_sql(conn)
    print()

    imported = 0
    for table in TABLES:
        csv_path = CSV_DIR / f"{table}.csv"
        if not csv_path.exists():
            print(f"⏭️  {table} — no CSV found at {csv_path.name}, skipping")
            continue

        count = _import_csv(conn, table, csv_path)
        size = _human_size(csv_path.stat().st_size)
        print(f"✅ {SCHEMA_NAME}.{table} — {count:,} rows loaded ({size})")
        imported += 1

    conn.close()
    print(f"\nDone. {imported} table(s) imported.")


if __name__ == "__main__":
    main()
