"""
Workshop bootstrap — raw → bronze ingest, single Wherobots job.

Ingests public geospatial raw data into Iceberg tables in the caller's
Wherobots org_catalog. Produces seven Bronze tables that the workshop's
bronze-to-silver.ipynb expects as inputs:

    org_catalog.noaa_swdi.{hail, tvs, structure, warn}
    org_catalog.opera.dswx_s1
    org_catalog.wildfire_risk.{burn_probability_conus, conditional_flame_length_conus}

Source data lives in two public buckets, both read anonymously:

    s3://wherobots-examples/aws-felt-wherobots-workshop/   (OPERA + USFS rasters)
    s3://noaa-swdi-pds/                                    (NOAA severe-weather CSVs)

The canonical copy of this script lives at:

    s3://wherobots-examples/aws-felt-wherobots-workshop/scripts/bootstrap.py

Submit as a Wherobots job run:

    curl -X POST 'https://api.cloud.wherobots.com/runs?region=aws-us-west-2' \\
      -H "X-API-Key: $WHEROBOTS_API_KEY" \\
      -H 'Content-Type: application/json' \\
      -d '{
        "runtime": "tiny",
        "name": "workshop-bootstrap",
        "runPython": {
          "uri": "s3://wherobots-examples/aws-felt-wherobots-workshop/scripts/bootstrap.py"
        },
        "timeoutSeconds": 1800
      }'

Expected wall clock: ~3.5 min on Tiny runtime. Idempotent — re-running replaces
the tables (no append semantics, no duplicate rows).
"""

import re
import time

from pyspark.sql.functions import col, expr, lit, regexp_extract, to_date, to_timestamp, udf
from pyspark.sql.types import StringType
from sedona.spark import SedonaContext


# ── Config ────────────────────────────────────────────────────────────────────

# Public workshop bucket — holds OPERA + USFS wildfire rasters
WORKSHOP_BASE = "s3://wherobots-examples/aws-felt-wherobots-workshop"

# NOAA SWDI is served directly from the NOAA public bucket
NOAA_BASE = "s3://noaa-swdi-pds"

# Output namespaces — caller's own org_catalog
NS_NOAA = "org_catalog.noaa_swdi"
NS_OPERA = "org_catalog.opera"
NS_WILDFIRE = "org_catalog.wildfire_risk"

# Raster chip size (matches the sedona-native pattern in bronze-to-silver)
TILE_SIZE = 128

# SWDI scope — workshop's WEATHER_WINDOW runs 2025-01-01 → 2026-03-25.
# 2024 is included as a buffer year for participants who want to widen the
# silver-to-gold window post-workshop. 2026 annual rollup isn't published yet
# (NOAA releases annual files ~2 months after year-end).
#
# To ingest more history (e.g., the full 1995–2025 archive), edit this list
# and re-submit — adds ~2–3 min to the job per ~10 years of data.
SWDI_YEARS = ["2024", "2025"]


# ── Sedona context with anonymous S3 reads on both public buckets ─────────────
#
# Anonymous credentials make the script portable across every Wherobots org:
# the compute role doesn't need a bucket-policy grant on either source bucket.

config = (
    SedonaContext.builder()
    .config(
        "spark.hadoop.fs.s3a.bucket.noaa-swdi-pds.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.AnonymousAWSCredentialsProvider",
    )
    .config(
        "spark.hadoop.fs.s3a.bucket.wherobots-examples.aws.credentials.provider",
        "org.apache.hadoop.fs.s3a.AnonymousAWSCredentialsProvider",
    )
    .config("spark.ui.showConsoleProgress", "false")
    .getOrCreate()
)
config.sparkContext.setLogLevel("ERROR")  # participants read this log; keep it to our own progress lines and real errors
sedona = SedonaContext.create(config)


def step(name: str) -> float:
    print(f"\n=== {name} ===", flush=True)
    return time.time()


def done(t0: float, label: str) -> None:
    print(f"  ✓ {label} in {time.time() - t0:.1f}s", flush=True)


# ── 1. NOAA SWDI — point datasets (hail, tvs, structure) ──────────────────────

sedona.sql(f"CREATE DATABASE IF NOT EXISTS {NS_NOAA}")

POINT_DATASETS = {
    "hail": {
        "columns": ["ZTIME", "LON", "LAT", "WSR_ID", "CELL_ID",
                    "RANGE", "AZIMUTH", "SEVPROB", "PROB", "MAXSIZE"],
        "casts": {"RANGE": "double", "AZIMUTH": "double",
                  "SEVPROB": "double", "PROB": "double", "MAXSIZE": "double"},
    },
    "tvs": {
        "columns": ["ZTIME", "LON", "LAT", "WSR_ID", "CELL_ID", "CELL_TYPE",
                    "RANGE", "AZIMUTH", "AVGDV", "LLDV", "MXDV", "MXDV_HEIGHT",
                    "DEPTH", "BASE", "TOP", "MAX_SHEAR", "MAX_SHEAR_HEIGHT"],
        "casts": {"RANGE": "double", "AZIMUTH": "double", "AVGDV": "double",
                  "LLDV": "double", "MXDV": "double", "MXDV_HEIGHT": "double",
                  "DEPTH": "double", "BASE": "double", "TOP": "double",
                  "MAX_SHEAR": "double", "MAX_SHEAR_HEIGHT": "double"},
    },
    "structure": {
        "columns": ["ZTIME", "LON", "LAT", "WSR_ID", "CELL_ID",
                    "RANGE", "AZIMUTH", "BASE_HEIGHT", "TOP_HEIGHT",
                    "VIL", "MAX_REFLECT", "HEIGHT"],
        "casts": {"RANGE": "double", "AZIMUTH": "double",
                  "BASE_HEIGHT": "double", "TOP_HEIGHT": "double",
                  "VIL": "double", "MAX_REFLECT": "double", "HEIGHT": "double"},
    },
}


def load_point_dataset(dataset: str, columns: list, casts: dict):
    paths = [f"{NOAA_BASE}/{dataset}-{y}.csv" for y in SWDI_YEARS]
    df = (
        sedona.read.option("comment", "#")
        .csv(paths)
        .toDF(*columns)
        .withColumn("ZTIME", to_timestamp(col("ZTIME"), "yyyyMMddHHmmss"))
    )
    for name, dtype in casts.items():
        df = df.withColumn(name, col(name).cast(dtype))
    return (
        df.withColumn("geometry", expr("ST_Point(CAST(LON AS DOUBLE), CAST(LAT AS DOUBLE))"))
          .drop("LON", "LAT")
    )


for dataset, spec in POINT_DATASETS.items():
    t0 = step(f"SWDI point: {dataset}")
    df = load_point_dataset(dataset, spec["columns"], spec["casts"])
    table = f"{NS_NOAA}.{dataset}"
    df.writeTo(table).createOrReplace()
    done(t0, table)


# ── 2. NOAA SWDI — warn (polygons, historical 2001–2016) ──────────────────────
#
# NOAA stopped publishing the annual warn-YYYY.csv files after 2016, so this
# table is a historical archive. It's included for catalog completeness; the
# workshop's bronze-to-silver pipeline does not currently join against it.
#
# Some polygons in the source have malformed WKT (missing commas between rings,
# comma-separated coord pairs instead of space-separated). _fix_wkt normalizes
# them so ST_GeomFromText can parse the whole file cleanly.

def _fix_wkt(s):
    if s is None:
        return None
    s = re.sub(r"\)\s+\(", "), (", s)

    def _fix_coords(m):
        content = m.group(1).replace(",", " ")
        nums = content.split()
        if len(nums) % 2 != 0:
            return m.group(0)
        pairs = [f"{nums[i]} {nums[i+1]}" for i in range(0, len(nums), 2)]
        return "(" + ", ".join(pairs) + ")"

    return re.sub(r"\(([^()]+)\)", _fix_coords, s)


fix_wkt = udf(_fix_wkt, StringType())

WARN_YEARS = [str(y) for y in range(2001, 2017)]
WARN_COLUMNS = ["ISSUEDATE", "EXPIREDATE", "ISSUEWFO",
                "MESSAGEID", "MESSAGETYPE", "WARNINGTYPE", "POLYGON"]

t0 = step("SWDI warn")
warn_paths = [f"{NOAA_BASE}/warn-{y}.csv" for y in WARN_YEARS]
warn_df = (
    sedona.read.option("comment", "#")
    .csv(warn_paths)
    .toDF(*WARN_COLUMNS)
    .withColumn("ISSUEDATE", to_timestamp(col("ISSUEDATE"), "yyyy-MM-dd HH:mm:ss.S"))
    .withColumn("EXPIREDATE", to_timestamp(col("EXPIREDATE"), "yyyy-MM-dd HH:mm:ss.S"))
    .withColumn("POLYGON", fix_wkt(col("POLYGON")))
    .withColumn("geometry", expr("ST_GeomFromText(POLYGON)"))
    .drop("POLYGON")
)
warn_table = f"{NS_NOAA}.warn"
warn_df.writeTo(warn_table).createOrReplace()
done(t0, warn_table)


# ── 3. OPERA DSWx-S1 ──────────────────────────────────────────────────────────

sedona.sql(f"CREATE DATABASE IF NOT EXISTS {NS_OPERA}")

DSWX_BASE = f"{WORKSHOP_BASE}/flood/opera_dswx_s1"
DSWX_BANDS = {"B01_WTR", "B02_BWTR", "B03_CONF", "B04_DIAG",
              "B05_WTR-1", "B06_WTR-2", "B07_LAND", "B08_SHAD"}

t0 = step("OPERA DSWx-S1: listing")
sc = sedona.sparkContext
hadoop = sc._jvm.org.apache.hadoop
fs_path = hadoop.fs.Path(DSWX_BASE)
fs = hadoop.fs.FileSystem.get(fs_path.toUri(), sc._jsc.hadoopConfiguration())

all_paths = []
iterator = fs.listFiles(fs_path, True)
while iterator.hasNext():
    p = iterator.next().getPath().toString().replace("s3a://", "s3://")
    if not p.endswith(".tif"):
        continue
    fname = p.split("/")[-1]
    if any(b in fname for b in DSWX_BANDS):
        all_paths.append(p)
print(f"  found {len(all_paths):,} DSWx-S1 GeoTIFFs", flush=True)
done(t0, "listing")

t0 = step("OPERA DSWx-S1: ingest")
dswx_df = (
    sedona.read.format("raster")
    .option("retile", False)
    .load(all_paths)
    .withColumnRenamed("rast", "raster")
    .withColumn("_path", expr("RS_BandPath(raster)"))
    .withColumn(
        "acq_date",
        to_date(regexp_extract("_path", r"_(\d{8})T\d{6}Z_", 1), "yyyyMMdd"),
    )
    .withColumn("band", regexp_extract("_path", r"_(B\d{2}_[A-Z0-9-]+)\.tif", 1))
    .drop("_path")
    .selectExpr(
        f"RS_TileExplode(raster, {TILE_SIZE}, {TILE_SIZE}) as (x, y, raster)",
        "band",
        "acq_date",
    )
    .withColumn("geometry", expr("RS_Envelope(raster)"))
    .withColumn("crs", lit("EPSG:32611"))
)
dswx_table = f"{NS_OPERA}.dswx_s1"
dswx_df.writeTo(dswx_table).createOrReplace()
done(t0, dswx_table)


# ── 4. USFS wildfire rasters ──────────────────────────────────────────────────

sedona.sql(f"CREATE DATABASE IF NOT EXISTS {NS_WILDFIRE}")

WILDFIRE_DATASETS = {
    "burn_probability_conus":         f"{WORKSHOP_BASE}/wildfire/burn_probability_conus.tif",
    "conditional_flame_length_conus": f"{WORKSHOP_BASE}/wildfire/conditional_flame_length_conus.tif",
}

for table_name, s3_path in WILDFIRE_DATASETS.items():
    t0 = step(f"Wildfire: {table_name}")
    df = (
        sedona.read.format("raster")
        .option("tileWidth", TILE_SIZE)
        .option("tileHeight", TILE_SIZE)
        .load(s3_path)
        .withColumnRenamed("rast", "raster")
        .withColumn("geometry", expr("RS_Envelope(raster)"))
        .withColumn("crs", lit("EPSG:5070"))
    )
    table = f"{NS_WILDFIRE}.{table_name}"
    df.writeTo(table).createOrReplace()
    done(t0, table)


# ── 5. Verify ─────────────────────────────────────────────────────────────────

ALL_TABLES = [
    f"{NS_NOAA}.hail",
    f"{NS_NOAA}.tvs",
    f"{NS_NOAA}.structure",
    f"{NS_NOAA}.warn",
    f"{NS_OPERA}.dswx_s1",
    f"{NS_WILDFIRE}.burn_probability_conus",
    f"{NS_WILDFIRE}.conditional_flame_length_conus",
]

print("\n=== Bootstrap complete ===", flush=True)
print(f"{'Table':<55} {'Rows':>15}")
print("-" * 72)
for tbl in ALL_TABLES:
    n = sedona.table(tbl).count()
    print(f"{tbl:<55} {n:>15,}")

print("\n✓ Bronze layer ready. Next: run bronze-to-silver.ipynb in your Wherobots notebook.", flush=True)
