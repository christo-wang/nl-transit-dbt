-- Grain: one row per stop.
-- The reportable number. Weekly departures is the sum across service patterns,
-- each weighted by how many days a week that pattern actually runs.

with departures as (
    select * from {{ ref('fct_departures') }}
),

stops as (
    select * from {{ ref('stg_stops') }}
),

by_stop as (

    select
        stop_id,
        sum(departures_per_week)  as departures_per_week,
        max(distinct_routes)      as routes_serving_stop

    from departures
    group by 1

)

select
    stops.stop_id,
    stops.stop_name,
    stops.stop_latitude,
    stops.stop_longitude,
    coalesce(by_stop.departures_per_week, 0)  as departures_per_week,
    coalesce(by_stop.routes_serving_stop, 0)  as routes_serving_stop

from stops
left join by_stop on stops.stop_id = by_stop.stop_id
