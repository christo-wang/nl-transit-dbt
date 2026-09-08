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
| dbt model | 1,348 |

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

python ingest/load_raw.py --source fixture   # committed sample, ~2s
dbt build                                    # 30 tests
python ingest/reconcile.py
```

For the live national feed instead of the sample:

```bash
python ingest/load_raw.py --source feed      # ~200MB, clipped to Noord-Holland
```

No credentials, no cloud account, no `dbt deps`. Clone and run.

## Design notes

**Why DuckDB.** The warehouse is a single file, so the whole thing rebuilds from
source in seconds and GitHub Actions can run the full `dbt build` on every pull
request with no secrets and no compute bill. The trade-off is that DuckDB is
single-node and not what most teams run in production; the models are plain SQL
and the adapter is the only thing that would change.

**Why CI runs on a fixture.** `fixtures/gtfs/` holds a small hand-built sample
covering the shapes that matter, including a trip departing at `24:40:00`. A
pull request should not fail because a third-party server is down, and it should
not download 200MB on every push. The live feed is a local concern.

**Why raw is all VARCHAR.** `ingest/load_raw.py` types nothing. Casting is a
modelling decision, so a schema surprise upstream fails inside a model with a
readable error instead of silently at load time.

**Why the generic tests are hand-written.** `accepted_range` would normally come
from `dbt_utils`. Writing it locally keeps the project dependency-free, so setup
is `pip install -r requirements.txt` and nothing else. `rollup_reconciles` is
genuinely custom: it asserts that a measure summed at the child grain equals the
same measure at the parent grain.

**On GTFS times past midnight.** GTFS measures time from noon minus twelve hours
on the service day, so a bus leaving at 00:40 after a Friday service is written
`24:40:00` and belongs to Friday. Parsing that as a clock time either throws or
wraps it to 00:40 and moves the departure to the wrong day. `stg_stop_times`
converts to seconds since service start, and the range test on that column caps
at 30 hours rather than 24 — a 24-hour bound would fail on every night bus in
the country.

## Layout

```
ingest/load_raw.py      GTFS -> raw schema (fixture or live feed)
ingest/reconcile.py     legacy vs dbt, two classes of difference
legacy/service_level.sql  the inherited script, unchanged
models/staging/         one model per source, typed and renamed
models/intermediate/    stop-to-neighbourhood spatial join
models/marts/           fct_departures, service level by stop
macros/                 accepted_range, rollup_reconciles
fixtures/gtfs/          committed sample for CI
```

## Roadmap

- [x] Staging layer, tests, stop-level service mart
- [x] Legacy reconciliation, two classes of difference
- [x] CI on every pull request
- [ ] Spatial join: stops to CBS neighbourhood boundaries
- [ ] Rollup to wijk and gemeente
- [ ] Population denominators — departures per 1,000 residents
- [ ] Incremental materialisation on `fct_departures`
- [ ] Snapshot on route service level across feed versions

## Sources

- GTFS: [OVapi national aggregate feed](http://gtfs.ovapi.nl/gtfs-nl.zip),
  via the [Mobility Database](https://mobilitydatabase.org/feeds/gtfs/mdb-1077)
- Boundaries: [CBS Wijk- en Buurtkaart](https://www.cbs.nl/nl-nl/dossier/nederland-regionaal/geografische-data/wijk-en-buurtkaart),
  GeoPackage, EPSG:28992
