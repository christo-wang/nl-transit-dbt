-- Grain: one row per buurt (CBS neighbourhood).
-- Rolls stop-level weekly departures up to the neighbourhood each stop
-- physically sits inside, via the spatial join in int_stop_buurt.
--
-- int_stop_buurt is an inner join: a stop that falls outside every buurt
-- polygon (edge-of-bbox clipping, bad source data, a future CRS regression)
-- is dropped silently, not errored. That would show up here as this mart's
-- total being smaller than mart_service_level_by_stop's total -- which is
-- exactly what the rollup_reconciles test below checks for.

with stop_level as (

    select * from {{ ref('mart_service_level_by_stop') }}

),

stop_buurt as (

    select * from {{ ref('int_stop_buurt') }}

),

joined as (

    select
        stop_buurt.buurtcode,
        stop_buurt.buurtnaam,
        stop_buurt.wijkcode,
        stop_buurt.gemeentecode,
        stop_buurt.gemeentenaam,
        stop_level.stop_id,
        stop_level.departures_per_week

    from stop_level
    inner join stop_buurt on stop_level.stop_id = stop_buurt.stop_id

),

aggregated as (

    select
        buurtcode,
        buurtnaam,
        wijkcode,
        gemeentecode,
        gemeentenaam,
        count(distinct stop_id)           as stops_in_buurt,
        sum(departures_per_week)          as departures_per_week

    from joined
    group by 1, 2, 3, 4, 5

)

select * from aggregated
