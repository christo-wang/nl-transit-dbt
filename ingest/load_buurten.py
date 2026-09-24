"""Load CBS Wijk- en Buurtkaart boundaries into DuckDB, no DuckDB spatial
extension required.

DuckDB's spatial extension needs a network download of a GDAL-backed reader
to open a GeoPackage; where that download is unreachable (some sandboxed or
firewalled environments), this script routes around it entirely by using
geopandas/pyogrio (a pure-Python GDAL binding, no DuckDB extension involved)
to read the file, then hands DuckDB the geometry column as WKB bytes. Once
DuckDB's own spatial extension IS loaded downstream (stg_buurten and the
spatial join both need it), ST_GeomFromWKB reconstitutes real geometry from
those bytes — no information is lost by loading this way.

Usage:
    python ingest/load_buurten.py
"""

import pathlib

import duckdb
import geopandas as gpd

GPKG_PATH = pathlib.Path("data/raw/wijkenbuurten_2024_v2.gpkg")
DB_PATH = "dev.duckdb"

# The GeoPackage carries ~150 columns of general CBS demographic profile data
# (house prices, distance to nearest cinema, etc.) alongside the boundaries.
# This project only ever needs the join keys, the name, population, and the
# geometry itself — loading all ~150 into `raw` would be verbatim-fidelity
# for its own sake at real cost (the file is 230MB) with no project benefit.
# This is a deliberate, documented exception to "raw is loaded verbatim."
KEEP_COLUMNS = [
    "buurtcode",
    "buurtnaam",
    "wijkcode",
    "gemeentecode",
    "gemeentenaam",
    "aantal_inwoners",
    "geometry",
]


def main() -> None:
    print(f"reading {GPKG_PATH} (layer=buurten) ...")
    gdf = gpd.read_file(GPKG_PATH, layer="buurten", columns=KEEP_COLUMNS[:-1])
    print(f"  {len(gdf):,} rows, CRS = {gdf.crs}")

    # WKB bytes travel through DuckDB as an ordinary BLOB column with no
    # spatial extension involved. ST_GeomFromWKB (spatial extension) turns
    # this back into a real GEOMETRY value downstream, in stg_buurten.
    gdf["geometry_wkb"] = gdf.geometry.apply(lambda g: g.wkb)
    df = gdf.drop(columns="geometry").rename(columns={"geometry_wkb": "geometry"})

    con = duckdb.connect(DB_PATH)
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.register("buurten_df", df)
    con.execute("CREATE OR REPLACE TABLE raw.buurten AS SELECT * FROM buurten_df")
    n = con.execute("SELECT count(*) FROM raw.buurten").fetchone()[0]
    print(f"  loaded raw.buurten: {n:,} rows")
    con.close()


if __name__ == "__main__":
    main()
