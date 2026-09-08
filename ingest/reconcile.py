"""Compare the legacy script's output against the dbt mart.

Two classes of difference, and they are treated differently:

  MUST BE ZERO      - the set of stops. If the refactor drops or invents a
                      stop, that is a defect and this exits non-zero.

  EXPLAINED         - the departure counts. These differ on purpose, because
                      the legacy script has a known bug. The difference is
                      reported and asserted against an expected direction,
                      not silently accepted.

Run after `dbt build`.
"""

import sys

import duckdb

DB_PATH = "dev.duckdb"
LEGACY_SQL = "legacy/service_level.sql"


def main() -> int:
    con = duckdb.connect(DB_PATH)
    con.execute(open(LEGACY_SQL).read())

    key_diff = con.execute(
        """
        select
            count(*) filter (where m.stop_id is null) as only_in_legacy,
            count(*) filter (where l.stop_id is null) as only_in_dbt
        from legacy_service_level l
        full outer join main.mart_service_level_by_stop m
            on l.stop_id = m.stop_id
        """
    ).fetchone()

    totals = con.execute(
        """
        select
            (select sum(departures_per_week) from legacy_service_level),
            (select sum(departures_per_week) from main.mart_service_level_by_stop)
        """
    ).fetchone()

    print("key reconciliation")
    print(f"  stops only in legacy : {key_diff[0]}")
    print(f"  stops only in dbt    : {key_diff[1]}")
    print("measure reconciliation")
    print(f"  legacy weekly departures : {totals[0]:,}")
    print(f"  dbt weekly departures    : {totals[1]:,.0f}")
    print(
        "  explained by: legacy counts each scheduled departure once, "
        "regardless of how many days per week the service pattern runs."
    )

    failed = False
    if key_diff[0] or key_diff[1]:
        print("FAIL: stop keys do not reconcile", file=sys.stderr)
        failed = True
    if totals[1] < totals[0]:
        print("FAIL: day-weighting should raise the total, not lower it", file=sys.stderr)
        failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
