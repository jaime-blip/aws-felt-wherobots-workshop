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

# SWDI scope — the annual files end 2025-12-31, and the workshop's WEATHER_WINDOW ends there too.
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
    # A handful of source polygons survive the WKT repair with coordinates far
    # outside any NWS forecast area (east of 60 W, south of 15 N); drop them so
    # the table's extent means something.
    .filter("ST_XMin(geometry) >= -180 AND ST_XMax(geometry) <= -60 AND ST_YMin(geometry) >= 15 AND ST_YMax(geometry) <= 72")
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


# ── 5. Verify and document ────────────────────────────────────────────────────
#
# Each Bronze table carries its own documentation: Iceberg table properties and
# column comments following the Wherobots table-metadata convention (comment,
# source, source_url, datetime.*, query.*, geo.*). The Wherobots MCP
# describe_table tool returns them, so an agent learns what a row is, its units
# and its coverage without running a query. Everything measurable (row count,
# time coverage, bounding box, resolution, band list) is computed from the table
# just written so it cannot drift from the data. The prose stays short and
# source_url points at the producer's documentation for the rest.

SWDI_SOURCE = "NOAA NCEI Severe Weather Data Inventory (NEXRAD Level III products)"
SWDI_URL = "https://www.ncei.noaa.gov/products/severe-weather-data-inventory"
SWDI_JOIN = "WSR_ID,CELL_ID,ZTIME"
SWDI_COLUMNS = {
    "ZTIME": "Radar volume scan time, UTC (scans repeat every 4 to 6 minutes). Not unique: "
             "many cells per scan, and every radar that sees a storm reports it.",
    "WSR_ID": "NEXRAD radar site that made the detection, e.g. KNKX for San Diego.",
    "CELL_ID": "Storm cell label assigned by the radar's cell identification algorithm; reused across scans and radars.",
    "RANGE": "Distance from the radar to the cell, nautical miles.",
    "AZIMUTH": "Bearing from the radar to the cell, degrees clockwise from north.",
    "geometry": "Location NOAA reports for the detection, as a point in EPSG:4326 (longitude, latitude).",
}

OPERA_URL = "https://www.jpl.nasa.gov/go/opera/products/dswx-product-suite/"
WRC_URL = "https://doi.org/10.2737/RDS-2020-0016-2"
WRC_SOURCE = "USFS Wildfire Risk to Communities, 2nd edition (Scott et al. 2024)"

TABLE_DOCS = {
    f"{NS_NOAA}.hail": {
        "time_col": "ZTIME",
        "comment": "NEXRAD hail signatures: one row per storm cell per radar scan where the hail algorithm "
                   "found hail, US-wide. MAXSIZE is the estimated maximum hail size in inches; "
                   "MAXSIZE >= 1 is the NWS severe-hail criterion. The same storm appears once per radar that sees it.",
        "props": {"source": SWDI_SOURCE, "source_url": SWDI_URL, "query.join_key": SWDI_JOIN,
                  "query.hint": "Filter ZTIME first, then by distance (ST_DWithin on geography, or ST_KNN). "
                                "Count distinct CELL_ID per WSR_ID to avoid double counting across radars."},
        "columns": {**SWDI_COLUMNS,
                    "SEVPROB": "Probability that the cell contains severe hail (1 inch or larger), percent.",
                    "PROB": "Probability that the cell contains hail of any size, percent.",
                    "MAXSIZE": "Estimated maximum hail size, inches."},
    },
    f"{NS_NOAA}.tvs": {
        "time_col": "ZTIME",
        "comment": "NEXRAD tornado vortex signatures: one row per detected low-level rotation signature per radar "
                   "scan, US-wide. A TVS is a radar signature of possible tornadic rotation, not a confirmed tornado. "
                   "Rare compared with hail and storm cells.",
        "props": {"source": SWDI_SOURCE, "source_url": SWDI_URL, "query.join_key": SWDI_JOIN,
                  "query.hint": "Filter ZTIME first. Expect few rows in any one county; MXDV (knots) is the strength measure."},
        "columns": {**SWDI_COLUMNS,
                    "CELL_TYPE": "TVS for a tornado vortex signature, ETVS for an elevated one (rotation not reaching the lowest scan).",
                    "AVGDV": "Average gate-to-gate velocity difference across the signature, knots.",
                    "LLDV": "Low-level velocity difference, knots.",
                    "MXDV": "Maximum velocity difference, knots; the signature's strength.",
                    "MXDV_HEIGHT": "Height of the maximum velocity difference, thousands of feet.",
                    "DEPTH": "Vertical depth of the signature, thousands of feet.",
                    "BASE": "Height of the signature base, thousands of feet.",
                    "TOP": "Height of the signature top, thousands of feet.",
                    "MAX_SHEAR": "Maximum shear, in units of 0.001 per second.",
                    "MAX_SHEAR_HEIGHT": "Height of the maximum shear, thousands of feet."},
    },
    f"{NS_NOAA}.structure": {
        "time_col": "ZTIME",
        "comment": "NEXRAD storm cell structure: one row per radar-identified storm cell per radar scan, US-wide, "
                   "of any intensity. These are storm cells, not mesocyclones. MAX_REFLECT >= 45 dBZ matches "
                   "NCEI's own filtered storm-cell set; VIL is a storm intensity proxy. "
                   "The same storm appears once per radar that sees it.",
        "props": {"source": SWDI_SOURCE, "source_url": SWDI_URL, "query.join_key": SWDI_JOIN,
                  "query.hint": "Filter ZTIME first and consider MAX_REFLECT >= 45 or VIL thresholds; "
                                "unfiltered rows include weak cells. Largest SWDI table."},
        "columns": {**SWDI_COLUMNS,
                    "BASE_HEIGHT": "Height of the cell base, thousands of feet.",
                    "TOP_HEIGHT": "Height of the cell top, thousands of feet.",
                    "VIL": "Vertically integrated liquid, kg per square metre; higher values indicate more intense storms.",
                    "MAX_REFLECT": "Maximum reflectivity in the cell, dBZ; 45 and above is a strong storm, 55 and above suggests large hail.",
                    "HEIGHT": "Height of the maximum reflectivity, thousands of feet."},
    },
    f"{NS_NOAA}.warn": {
        "time_col": "ISSUEDATE",
        "comment": "NWS severe thunderstorm, tornado, flash flood and special marine warning polygons, archive "
                   "2001 to 2016 (NOAA stopped the annual files after 2016). Not used by the workshop pipeline "
                   "and not contemporaneous with the radar tables.",
        "props": {"source": "NOAA NCEI Severe Weather Data Inventory (NWS warnings)", "source_url": SWDI_URL,
                  "query.hint": "Filter WARNINGTYPE and ISSUEDATE; a warning is active between ISSUEDATE and EXPIREDATE."},
        "columns": {"ISSUEDATE": "Time the warning was issued, UTC.",
                    "EXPIREDATE": "Time the warning expired, UTC.",
                    "ISSUEWFO": "NWS forecast office that issued it, e.g. SGX for San Diego.",
                    "MESSAGEID": "NWS message identifier.",
                    "MESSAGETYPE": "Message type code from the NWS product.",
                    "WARNINGTYPE": "Warning category code: severe thunderstorm, tornado, flash flood or special marine.",
                    "geometry": "Warning polygon, EPSG:4326."},
    },
    f"{NS_OPERA}.dswx_s1": {
        "time_col": "acq_date",
        "raster": True,
        "band_col": "band",
        "comment": "OPERA DSWx-S1 surface water from Sentinel-1 radar, 30 m, workshop subset around San Diego "
                   "(see geo.bbox and datetime.*). One row per 128x128-pixel tile per layer per acquisition; "
                   "filter band = 'B01_WTR' and acq_date. In B01_WTR, water is class 1 (open water) or 3 "
                   "(inundated vegetation); 250 is HAND-masked high ground and 251 radar layover/shadow, both unobserved, not water; 255 is no data. Revisit 6 to 12 days.",
        "props": {"source": "NASA JPL OPERA (Sentinel-1 RTC input), distributed by PO.DAAC", "source_url": OPERA_URL,
                  "query.hint": "Always filter band and acq_date. Use RS_ZonalStats / RS_Intersects with EPSG:4326 "
                                "geometries; Sedona reprojects. Treat only classes 1 and 3 as water."},
        "columns": {"x": "Tile column index within the source scene (from RS_TileExplode).",
                    "y": "Tile row index within the source scene.",
                    "raster": "128x128-pixel UInt8 tile of one DSWx-S1 layer, UTM zone 11N.",
                    "band": "DSWx-S1 layer: B01_WTR water classes, B02_BWTR binary water, B03_CONF confidence, "
                            "B04_DIAG diagnostics (see geo.raster.bands for the layers present).",
                    "acq_date": "Sentinel-1 acquisition date, UTC.",
                    "geometry": "Tile footprint in the raster's CRS.",
                    "crs": "CRS of the tile, EPSG:32611 (UTM 11N) for the San Diego tiles."},
    },
    f"{NS_WILDFIRE}.burn_probability_conus": {
        "raster": True,
        "band_names": "BP",
        "datetime": ("2020-12-31", "2020-12-31"),
        "comment": "USFS Wildfire Risk to Communities annual burn probability, 30 m, continental US; landscape "
                   "conditions as of end of 2020. Pixel value is the probability of wildfire in a given year "
                   "(0 to 0.13). Tiled 128x128 pixels in EPSG:5070 (Albers).",
        "props": {"source": WRC_SOURCE, "source_url": WRC_URL,
                  "query.hint": "Use RS_ZonalStats(raster, geometry, 1, 'mean', true) per footprint; Sedona reprojects "
                                "EPSG:4326 geometries. Static product: no time filter."},
        "columns": {"raster": "128x128-pixel Float32 tile; annual burn probability, dimensionless.",
                    "x": "Tile column index within the source raster.",
                    "y": "Tile row index within the source raster.",
                    "name": "Source GeoTIFF the tile was cut from.",
                    "geometry": "Tile footprint in the raster's CRS.",
                    "crs": "CRS of the tile, EPSG:5070."},
    },
    f"{NS_WILDFIRE}.conditional_flame_length_conus": {
        "raster": True,
        "band_names": "CFL",
        "datetime": ("2022-12-31", "2022-12-31"),
        "comment": "USFS Wildfire Risk to Communities conditional flame length, 30 m, continental US; landscape "
                   "conditions as of end of 2022. Pixel value is the mean flame length in feet if a fire occurs "
                   "(0 to 408), a wildfire intensity measure. Tiled 128x128 pixels in EPSG:5070 (Albers).",
        "props": {"source": WRC_SOURCE, "source_url": WRC_URL,
                  "query.hint": "Use RS_ZonalStats(raster, geometry, 1, 'mean', true) per footprint; Sedona reprojects "
                                "EPSG:4326 geometries. Static product: no time filter."},
        "columns": {"raster": "128x128-pixel Float32 tile; conditional flame length, feet.",
                    "x": "Tile column index within the source raster.",
                    "y": "Tile row index within the source raster.",
                    "name": "Source GeoTIFF the tile was cut from.",
                    "geometry": "Tile footprint in the raster's CRS.",
                    "crs": "CRS of the tile, EPSG:5070."},
    },
}


def _q(s) -> str:
    return str(s).replace("'", "''")


def measure(table: str, spec: dict) -> dict:
    """Row count, temporal coverage, bounding box and raster facts, read from the table itself."""
    tcol = spec.get("time_col")
    time_sel = f"MIN({tcol}) AS t0, MAX({tcol}) AS t1" if tcol else "NULL AS t0, NULL AS t1"
    row = sedona.sql(f"""
        SELECT COUNT(*) AS n, {time_sel},
               MIN(ST_XMin(geometry)) AS xmin, MIN(ST_YMin(geometry)) AS ymin,
               MAX(ST_XMax(geometry)) AS xmax, MAX(ST_YMax(geometry)) AS ymax
        FROM {table}""").first()
    facts = {"n": row["n"]}
    if tcol:
        facts["datetime.start"] = str(row["t0"])[:10]
        facts["datetime.end"] = str(row["t1"])[:10]
    elif spec.get("datetime"):
        facts["datetime.start"], facts["datetime.end"] = spec["datetime"]

    bbox = (row["xmin"], row["ymin"], row["xmax"], row["ymax"])
    crs = "EPSG:4326"
    if spec.get("raster"):
        first = sedona.sql(f"SELECT RS_SRID(raster) AS srid, ABS(RS_ScaleX(raster)) AS res FROM {table} LIMIT 1").first()
        crs = f"EPSG:{first['srid']}"
        facts["geo.raster.resolution"] = f"{first['res']:g}"
        if spec.get("band_col"):
            bands = [r[0] for r in sedona.sql(f"SELECT DISTINCT {spec['band_col']} FROM {table} ORDER BY 1").collect()]
            facts["geo.raster.bands"] = ",".join(bands)
        else:
            facts["geo.raster.bands"] = spec["band_names"]
        if max(abs(bbox[0]), abs(bbox[2])) > 360:  # footprints stored in the raster CRS: express the bbox in EPSG:4326
            env = sedona.sql(f"""
                SELECT ST_Transform(ST_SetSRID(ST_PolygonFromEnvelope({bbox[0]}, {bbox[1]}, {bbox[2]}, {bbox[3]}), {first['srid']}),
                                    '{crs}', 'EPSG:4326') AS g""").first()["g"]
            bbox = env.bounds
        types = "Polygon"
    else:
        types = ",".join(sorted(r[0] for r in sedona.sql(f"SELECT DISTINCT GeometryType(geometry) FROM {table}").collect()))
        types = ",".join(t[0] + t[1:].lower() if t.startswith("MULTI") else t.capitalize() for t in types.split(","))
        types = types.replace("Multipolygon", "MultiPolygon").replace("Multipoint", "MultiPoint")
    if abs(bbox[1]) > 90:  # transform returned lat/lon order
        bbox = (bbox[1], bbox[0], bbox[3], bbox[2])
    facts["geo.crs"] = crs
    facts["geo.bbox"] = ",".join(f"{v:.3f}" for v in bbox)
    facts["geo.geometry_types"] = types
    return facts


def document(table: str, spec: dict, facts: dict) -> None:
    # Spark treats 'comment' and 'owner' as reserved table properties: the comment is
    # set with COMMENT ON TABLE (DESCRIBE TABLE EXTENDED shows it; SHOW TBLPROPERTIES
    # hides reserved keys), and 'owner' cannot be set at all (Spark rejects it and
    # records the current user itself).
    sedona.sql(f"COMMENT ON TABLE {table} IS '{_q(spec['comment'])}'")
    props = {**spec["props"], **{k: v for k, v in facts.items() if k != "n"}}
    kv = ", ".join(f"'{_q(k)}' = '{_q(v)}'" for k, v in props.items())
    sedona.sql(f"ALTER TABLE {table} SET TBLPROPERTIES ({kv})")
    for column, doc in spec["columns"].items():
        sedona.sql(f"ALTER TABLE {table} ALTER COLUMN {column} COMMENT '{_q(doc)}'")


print("\n=== Bootstrap complete ===", flush=True)
print(f"{'Table':<55} {'Rows':>15}  Coverage", flush=True)
print("-" * 100, flush=True)
for tbl, spec in TABLE_DOCS.items():
    facts = measure(tbl, spec)
    document(tbl, spec, facts)
    span = f"{facts.get('datetime.start', '')} to {facts.get('datetime.end', '')}".strip(" to")
    print(f"{tbl:<55} {facts['n']:>15,}  {span}  bbox {facts['geo.bbox']}", flush=True)

print("\n✓ Bronze layer ready and documented (describe any table to see its properties and column comments).", flush=True)
print("  Next: run bronze-to-silver.ipynb in your Wherobots notebook.", flush=True)
