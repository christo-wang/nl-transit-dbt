with stop_times as (
    select * from {{ ref('stg_stop_times') }}
),

trips as (
    select * from {{ ref('stg_trips') }}
),

calendar as (
    select * from {{ ref('stg_calendar') }}
),

routes as (
    select * from {{ ref('stg_routes') }}
),

joined as (

    select
        stop_times.stop_id,
        trips.service_id,
        trips.route_id,
        routes.route_category,
        calendar.days_per_week,
        stop_times.departure_seconds

    from stop_times
    inner join trips    on stop_times.trip_id  = trips.trip_id
    inner join calendar on trips.service_id    = calendar.service_id
    inner join routes   on trips.route_id      = routes.route_id

),

aggregated as (

    select
        stop_id,
        service_id,
        route_category,
        days_per_week,
        count(*)                        as departures_per_service_day,
        count(distinct route_id)        as distinct_routes,
        count(*) * days_per_week        as departures_per_week

    from joined
    group by 1, 2, 3, 4

)

select * from aggregated
