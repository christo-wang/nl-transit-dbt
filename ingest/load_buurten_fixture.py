"""Load a small synthetic buurten fixture into DuckDB, for CI.

CI cannot download the real 230MB CBS GeoPackage on every push -- same
reason load_raw.py has a --source fixture mode for GTFS. This draws a tiny
square polygon around each fixture stop's coordinates instead, tagged with
the real buurt/gemeente names those stops actually sit inside (confirmed
against the real CBS data during development), so the spatial join in CI
has something real-shaped to match against rather than an empty table that
happens to exist.

The buurtcode/wijkcode values in fixtures/buurten/buurten.csv are fixture
placeholders (BU_FIX_xxx / WK_FIX_xx) -- not real CBS codes. gemeentecode
values ARE real (GM0392 Haarlem, GM0363 Amsterdam, GM0479 Zaanstad,
GM0394 Haarlemmermeer) since those don't change project to project.

This deliberately reuses ST_Transform(..., always_xy := true) -- the same
call int_stop_buurt.sql makes -- so a regression that reintroduces the
EPSG:4326 axis-order bug shows up as a CI failure (rollup_reconciles on
mart_service_level_by_buurt), not just a silent local one.

Usage:
    python ingest/load_buurten_fixture.py
"""

import csv
import pathlib

import duckdb

FIXTURE_PATH = pathlib.Path("fixtures/buurten/buurten.csv")
DB_PATH = "dev.duckdb"

# Half-width of the square drawn around each stop, in degrees. ~0.003 deg is
# roughly 300m at this latitude: comfortably bigger than any float rounding
# in the fixture coordinates, small enough that neighbouring fixture squares
# don't overlap.
HALF_WIDTH_DEG = 0.003


def square_wkt(lon: float, lat: float, half_width: float) -> str:
    x0, x1 = lon - half_width, lon + half_width
    y0, y1 = lat - half_width, lat + half_width
    return f"POLYGON(({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))"


def main() -> None:
    con = duckdb.connect(DB_PATH)
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")

    with open(FIXTURE_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    con.execute("""
        CREATE OR REPLACE TABLE raw.buurten (
            buurtcode VARCHAR,
            buurtnaam VARCHAR,
            wijkcode VARCHAR,
            gemeentecode VARCHAR,
            gemeentenaam VARCHAR,
            aantal_inwoners INTEGER,
            geometry BLOB
        )
    """)

    for row in rows:
        wkt = square_wkt(float(row["center_lon"]), float(row["center_lat"]), HALF_WIDTH_DEG)
        con.execute(
            """
            INSERT INTO raw.buurten
            SELECT ?, ?, ?, ?, ?, ?,
                   ST_AsWKB(
                       ST_Transform(ST_GeomFromText(?), 'EPSG:4326', 'EPSG:28992', always_xy := true)
                   )
            """,
            [
                row["buurtcode"], row["buurtnaam"], row["wijkcode"],
                row["gemeentecode"], row["gemeentenaam"], int(row["aantal_inwoners"]),
                wkt,
            ],
        )

    n = con.execute("SELECT count(*) FROM raw.buurten").fetchone()[0]
    print(f"loaded raw.buurten: {n:,} rows (fixture squares, ~{HALF_WIDTH_DEG * 2 * 111:.0f}km wide)")
    con.close()


if __name__ == "__main__":
    main()
