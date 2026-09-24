# nl-transit-dbt

Migrating an inherited, untested SQL script into a tested dbt project — and
proving what the refactor changed.

The reporting question: **how much scheduled public transport actually serves a
given place?** Measured as weekly scheduled departures, from the Dutch national
GTFS feed, aggregated to CBS neighbourhood boundaries.

## The finding

The inherited script in `legacy/` produces a weekly-departures figure that has
been quoted in reporting. It is wrong, and it is wrong in a way that does not
look wrong:

| | weekly departures |
|---|---|
| legacy script | 436 |
| dbt model | 1,441 |

The legacy query counts each scheduled departure once. But GTFS describes a
*service pattern*, not a week — a trip on `SVC_SUN` runs once a week, a trip on
`SVC_WEEKDAY` runs five times. Counting rows treats them as equal. The number
was plausible, internally consistent, and had no test asserting otherwise.

`ingest/reconcile.py` splits the comparison into two classes and treats them
differently:

- **must be zero** — the set of stops. If the refactor drops or invents a stop,
  that is a defect and CI fails.
- **explained** — the measure. It differs on purpose, the direction is asserted,
  and the reason is printed on every run.

A refactor that silently produces a different number is not a refactor. This is
the difference between changing a number and *changing a number on the record*.

## Running it

```bash
pip install -r requirements.txt
export DBT_PROFILES_DIR=.

python ingest/load_raw.py --source fixture         # GTFS committed sample, ~2s
python ingest/load_buurten_fixture.py               # CBS boundaries committed sample, ~1s
dbt build
python ingest/reconcile.py
```

For the live national feed and the real CBS boundaries instead of the samples:

```bash
python ingest/load_raw.py --source feed             # ~200MB, clipped to Noord-Holland
python ingest/load_buurten.py                        # needs data/raw/wijkenbuurten_2024_v2.gpkg
                                                       # and `pip install geopandas` (not in
                                                       # requirements.txt — see Design notes)
```

No credentials, no cloud account, no `dbt deps`. Clone and run.

## Design notes

**Why DuckDB.** The warehouse is a single file, so the whole thing rebuilds from
source in seconds and GitHub Actions can run the full `dbt build` on every pull
request with no secrets and no compute bill. The trade-off is that DuckDB is
single-node and not what most teams run in production; the models are plain SQL
and the adapter is the only thing that would change.

**Why CI runs on fixtures.** `fixtures/gtfs/` holds a small hand-built GTFS
sample covering the shapes that matter, including a trip departing at
`24:40:00`. `fixtures/buurten/` holds twelve small synthetic squares, one drawn
around each fixture stop and tagged with the real neighbourhood/municipality
name that stop actually sits inside (confirmed against the real CBS data
during development). A pull request should not fail because a third-party
server is down, and it should not download 200MB of GTFS plus 230MB of CBS
boundaries on every push — but the fixture still has to exercise the same
spatial-join code path as production, not just stand a table up. See "the
EPSG:4326 bug" below for why that distinction mattered in practice.

**Why raw is all VARCHAR.** `ingest/load_raw.py` types nothing. Casting is a
modelling decision, so a schema surprise upstream fails inside a model with a
readable error instead of silently at load time.

**Why the generic tests are hand-written.** `accepted_range` would normally come
from `dbt_utils`. Writing it locally keeps the project dependency-free, so setup
is `pip install -r requirements.txt` and nothing else. `rollup_reconciles` is
genuinely custom: it asserts that a measure summed at the child grain equals the
same measure at the parent grain — used twice: stop vs. fact, and buurt vs.
stop.

**On GTFS times past midnight.** GTFS measures time from noon minus twelve hours
on the service day, so a bus leaving at 00:40 after a Friday service is written
`24:40:00` and belongs to Friday. Parsing that as a clock time either throws or
wraps it to 00:40 and moves the departure to the wrong day. `stg_stop_times`
converts to seconds since service start, and the range test on that column caps
at 30 hours rather than 24 — a 24-hour bound would fail on every night bus in
the country.

**Why `calendar_dates.txt`, not `calendar.txt`.** GTFS supports two ways to
describe a service pattern's schedule: a repeating weekly rule (`calendar.txt`)
or an explicit flat list of active dates (`calendar_dates.txt`). OVapi's real
feed ships only the latter — confirmed by inspecting the feed directly, not
assumed. `days_per_week` is therefore computed by counting each service
pattern's active dates and dividing by the calendar span the feed covers,
rather than summing weekday flags. This is a genuine behavioural difference
from a `calendar.txt`-based feed, not a workaround, and it's the reason
`stg_calendar.sql` and `legacy/service_level.sql` both changed after the
project moved from the committed fixture to a real feed sample.

**The EPSG:4326 axis-order bug.** `int_stop_buurt.sql` joins a GTFS stop
(WGS84 degrees, `stop_longitude`/`stop_latitude`) to a CBS neighbourhood
polygon (EPSG:28992 metres) by reprojecting the point with `ST_Transform`
before comparing them. The first version compiled cleanly, and every test in
the project passed — `40/40`, no errors — while the join itself matched
**zero** stops to any of the 14,668 real polygons. `unique`/`not_null` on an
empty result set is trivially true, so nothing caught it directly; only a
manual row count did.

The cause: EPSG:4326's *official* axis order, as defined by the standards
body, is (latitude, longitude) — backwards from the (x, y) = (longitude,
latitude) order almost every GIS tool, including `ST_Point` here, actually
writes points in. Passing explicit source/target CRS strings to
`ST_Transform` makes DuckDB's underlying PROJ library enforce that official
order, so it silently read the point backwards and reprojected it roughly
1,300km from where the stop actually is. The fix is `always_xy := true`,
which tells `ST_Transform` "trust the axis order I gave you" instead of the
authority's. See [duckdb/duckdb-spatial#474](https://github.com/duckdb/duckdb-spatial/issues/474)
for another user hitting the identical symptom.

Two things now guard against a regression: `ingest/load_buurten_fixture.py`
runs the identical `ST_Transform(..., always_xy := true)` call to build its
fixture polygons, so CI exercises the real code path; and
`rollup_reconciles` on `mart_service_level_by_buurt` fails loudly if the
spatial join ever again drops a stop it shouldn't.

## Layout

```
ingest/load_raw.py              GTFS -> raw schema (fixture or live feed)
ingest/load_buurten.py          CBS GeoPackage -> raw schema (real data, local only)
ingest/load_buurten_fixture.py  CBS boundaries -> raw schema (synthetic, CI)
ingest/reconcile.py             legacy vs dbt, two classes of difference
legacy/service_level.sql        the inherited script, unchanged
models/staging/                 one model per source, typed and renamed
models/intermediate/            stop-to-neighbourhood spatial join
models/marts/                   fct_departures, service level by stop and by buurt
macros/                         accepted_range, rollup_reconciles
fixtures/gtfs/                  committed GTFS sample for CI
fixtures/buurten/                committed boundaries sample for CI
```

## Roadmap

- [x] Staging layer, tests, stop-level service mart
- [x] Legacy reconciliation, two classes of difference
- [x] CI on every pull request
- [x] Spatial join: stops to CBS neighbourhood boundaries
- [x] Rollup to buurt (with wijk/gemeente keys carried through — a wijk- or
      gemeente-level mart is a `group by` on `mart_service_level_by_buurt`
      away, not yet built as its own model)
- [ ] Population denominators — departures per 1,000 residents
- [ ] Incremental materialisation on `fct_departures`
- [ ] Snapshot on route service level across feed versions

## Sources

- GTFS: [OVapi national aggregate feed](http://gtfs.ovapi.nl/gtfs-nl.zip),
  via the [Mobility Database](https://mobilitydatabase.org/feeds/gtfs/mdb-1077)
- Boundaries: [CBS Wijk- en Buurtkaart](https://www.cbs.nl/nl-nl/dossier/nederland-regionaal/geografische-data/wijk-en-buurtkaart),
  GeoPackage, EPSG:28992
