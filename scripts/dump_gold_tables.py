#!/usr/bin/env python3
"""Dump gold tables from Aurora PostgreSQL to CSV + DDL.

Authoring tool — used by workshop maintainers to snapshot a populated Aurora
into CSVs + a companion create_tables.sql. Geometry columns are exported as
WKT. Output lands in tmp/gold-dump/ (gitignored).

Reads AURORA_DSN from the project-root .env file.

The default workshop seed flow does NOT use this script — Part 1's pipeline
writes the gold tables, and CFN auto-seeds insurance_exposure from S3.
For that S3 seed refresh, use scripts/upload_seed_to_s3.sh instead.

Requirements:
    pip install psycopg2-binary python-dotenv
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "tmp" / "gold-dump"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GOLD_TABLES: list[str] = [
    "workshop.insurance_exposure",
    "workshop.cre_risk",
    "workshop.capmarkets_signals",
    "workshop.energy_infra_risk",
]

# Map PostgreSQL type OIDs / type names to SQL type strings used in DDL.
# geometry columns are detected separately via geometry_columns / column UDT.
PG_TYPE_MAP: dict[str, str] = {
    "smallint": "SMALLINT",
    "integer": "INTEGER",
    "bigint": "BIGINT",
    "real": "REAL",
    "double precision": "DOUBLE PRECISION",
    "numeric": "NUMERIC",
    "boolean": "BOOLEAN",
    "text": "TEXT",
    "character varying": "VARCHAR",
    "character": "CHAR",
    "date": "DATE",
    "timestamp without time zone": "TIMESTAMP",
    "timestamp with time zone": "TIMESTAMPTZ",
    "json": "JSON",
    "jsonb": "JSONB",
    "uuid": "UUID",
    "bytea": "BYTEA",
    "USER-DEFINED": "GEOMETRY",
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
    return psycopg2.connect(dsn)


def _schema_and_table(qualified: str) -> tuple[str, str]:
    """Split 'schema.table' into its parts."""
    schema, table = qualified.split(".", 1)
    return schema, table


def _get_columns(
    conn: psycopg2.extensions.connection,
    schema: str,
    table: str,
) -> list[dict]:
    """Return column metadata from information_schema.columns."""
    query = """
        SELECT
            column_name,
            data_type,
            udt_name,
            character_maximum_length,
            numeric_precision,
            numeric_scale,
            is_nullable
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name   = %s
        ORDER BY ordinal_position;
    """
    with conn.cursor() as cur:
        cur.execute(query, (schema, table))
        cols = cur.fetchall()

    result: list[dict] = []
    for col_name, data_type, udt_name, char_max, num_prec, num_scale, nullable in cols:
        result.append(
            {
                "name": col_name,
                "data_type": data_type,
                "udt_name": udt_name,
                "char_max": char_max,
                "num_prec": num_prec,
                "num_scale": num_scale,
                "nullable": nullable == "YES",
            }
        )
    return result


def _col_to_ddl_type(col: dict) -> str:
    """Map a column metadata dict to a SQL type string."""
    dt = col["data_type"]
    udt = col["udt_name"]

    # PostGIS geometry
    if dt == "USER-DEFINED" and udt == "geometry":
        return "GEOMETRY"

    # varchar with length
    if dt == "character varying" and col["char_max"]:
        return f"VARCHAR({col['char_max']})"

    # char with length
    if dt == "character" and col["char_max"]:
        return f"CHAR({col['char_max']})"

    # numeric with precision/scale
    if dt == "numeric" and col["num_prec"]:
        if col["num_scale"]:
            return f"NUMERIC({col['num_prec']},{col['num_scale']})"
        return f"NUMERIC({col['num_prec']})"

    # ARRAY types
    if dt == "ARRAY":
        base = udt.lstrip("_")
        return f"{PG_TYPE_MAP.get(base, base.upper())}[]"

    return PG_TYPE_MAP.get(dt, dt.upper())


def _build_select(columns: list[dict], schema: str, table: str) -> str:
    """Build a SELECT that casts geometry columns to WKT."""
    parts: list[str] = []
    for col in columns:
        if col["data_type"] == "USER-DEFINED" and col["udt_name"] == "geometry":
            parts.append(f'ST_AsText("{col["name"]}") AS "{col["name"]}"')
        else:
            parts.append(f'"{col["name"]}"')
    select_list = ",\n       ".join(parts)
    return f"SELECT {select_list}\nFROM {schema}.{table}"


def _export_table_to_csv(
    conn: psycopg2.extensions.connection,
    schema: str,
    table: str,
    columns: list[dict],
    dest: Path,
) -> int:
    """Export a single table to CSV using COPY (copy_expert). Returns row count."""
    select_sql = _build_select(columns, schema, table)
    copy_sql = f"COPY ({select_sql}) TO STDOUT WITH (FORMAT csv, HEADER true)"

    with open(dest, "w", newline="") as f:
        with conn.cursor() as cur:
            cur.copy_expert(copy_sql, f)

    # Count rows (subtract 1 for header)
    with open(dest) as f:
        row_count = sum(1 for _ in f) - 1
    return max(row_count, 0)


def _build_create_table(schema: str, table: str, columns: list[dict]) -> str:
    """Generate a CREATE TABLE statement from column metadata."""
    lines: list[str] = []
    for col in columns:
        type_str = _col_to_ddl_type(col)
        nullable_str = "" if col["nullable"] else " NOT NULL"
        lines.append(f'    "{col["name"]}" {type_str}{nullable_str}')

    body = ",\n".join(lines)
    return f'CREATE TABLE IF NOT EXISTS {schema}.{table} (\n{body}\n);\n'


def _human_size(nbytes: int) -> str:
    """Return a human-readable file size."""
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024  # type: ignore[assignment]
    return f"{nbytes:.1f} TB"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    conn = _connect()
    print(f"Connected to Aurora PostgreSQL.\n")

    ddl_statements: list[str] = []

    # Ensure schema exists in DDL
    ddl_statements.append("CREATE SCHEMA IF NOT EXISTS workshop;\n")
    ddl_statements.append("CREATE EXTENSION IF NOT EXISTS postgis;\n")

    for qualified in GOLD_TABLES:
        schema, table = _schema_and_table(qualified)
        columns = _get_columns(conn, schema, table)

        if not columns:
            print(f"WARNING: {qualified} — no columns found (table may not exist). Skipping.")
            continue

        # Export CSV
        csv_path = OUTPUT_DIR / f"{table}.csv"
        row_count = _export_table_to_csv(conn, schema, table, columns, csv_path)
        file_size = csv_path.stat().st_size

        print(f"{qualified}")
        print(f"  -> {csv_path.name}  ({row_count:,} rows, {_human_size(file_size)})")

        # Collect DDL
        ddl_statements.append(_build_create_table(schema, table, columns))

    # Write DDL file
    ddl_path = OUTPUT_DIR / "create_tables.sql"
    ddl_path.write_text("\n".join(ddl_statements))
    print(f"\nDDL written to {ddl_path.name}")

    conn.close()
    print("Done.")


if __name__ == "__main__":
    main()
