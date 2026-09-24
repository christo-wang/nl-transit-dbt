"""Load raw GTFS into DuckDB.

Two modes:

    python ingest/load_raw.py --source feed      # download the live OVapi feed
    python ingest/load_raw.py --source fixture   # load the committed sample

CI uses the fixture. A pull request should not depend on a third-party
server being up, and it should not pull 200MB on every push.
"""

import argparse
import io
import pathlib
import zipfile

import duckdb
import requests

FEED_URL = "http://gtfs.ovapi.nl/gtfs-nl.zip"
RAW_DIR = pathlib.Path("data/raw")
FIXTURE_DIR = pathlib.Path("fixtures/gtfs")
DB_PATH = "dev.duckdb"

# GTFS files this project reads. Anything else in the zip is ignored.
GTFS_FILES = ["stops.txt", "stop_times.txt", "trips.txt", "routes.txt", "calendar_dates.txt"]

# Bounding box for Noord-Holland, WGS84. Keeps the local build small enough
# to rebuild in seconds. Widen this to go national.
BBOX = {"min_lat": 52.20, "max_lat": 52.85, "min_lon": 4.35, "max_lon": 5.35}


def download_feed() -> pathlib.Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"downloading {FEED_URL} ...")
    resp = requests.get(FEED_URL, timeout=600)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        for name in GTFS_FILES:
            if name in zf.namelist():
                zf.extract(name, RAW_DIR)
                print(f"  extracted {name}")
            else:
                print(f"  WARNING: {name} not in feed")
    return RAW_DIR


def load(con: duckdb.DuckDBPyConnection, src: pathlib.Path, clip: bool) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    for name in GTFS_FILES:
        path = src / name
        table = f"raw.{name.removesuffix('.txt')}"
        if not path.exists():
            print(f"  skipping {name} (not present)")
            continue
        # all_varchar: GTFS is text by spec. Casting is the staging layer's job,
        # not the loader's. Keeping raw untyped means a schema surprise upstream
        # fails in a model with a readable error, not silently at load time.
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS "
            f"SELECT * FROM read_csv('{path}', all_varchar=true, header=true)"
        )
        n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        print(f"  loaded {table}: {n:,} rows")

    if clip:
        clip_to_bbox(con)


def clip_to_bbox(con: duckdb.DuckDBPyConnection) -> None:
    """Restrict the whole graph to stops inside the bounding box."""
    print("clipping to Noord-Holland bounding box ...")
    con.execute(
        f"""
        CREATE OR REPLACE TABLE raw.stops AS
        SELECT * FROM raw.stops
        WHERE TRY_CAST(stop_lat AS DOUBLE) BETWEEN {BBOX['min_lat']} AND {BBOX['max_lat']}
          AND TRY_CAST(stop_lon AS DOUBLE) BETWEEN {BBOX['min_lon']} AND {BBOX['max_lon']}
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE raw.stop_times AS
        SELECT st.* FROM raw.stop_times st
        SEMI JOIN raw.stops s ON s.stop_id = st.stop_id
        """
    )
    con.execute(
        """
        CREATE OR REPLACE TABLE raw.trips AS
        SELECT t.* FROM raw.trips t
        SEMI JOIN raw.stop_times st ON st.trip_id = t.trip_id
        """
    )
    for t in ["stops", "stop_times", "trips"]:
        n = con.execute(f"SELECT count(*) FROM raw.{t}").fetchone()[0]
        print(f"  raw.{t}: {n:,} rows after clip")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["feed", "fixture"], default="fixture")
    args = ap.parse_args()

    con = duckdb.connect(DB_PATH)
    if args.source == "feed":
        load(con, download_feed(), clip=True)
    else:
        load(con, FIXTURE_DIR, clip=False)
    con.close()
    print(f"done -> {DB_PATH}")


if __name__ == "__main__":
    main()
