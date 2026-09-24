with source as (

    select * from {{ source('raw', 'calendar_dates') }}

),

renamed as (

    select
        service_id,
        cast(strptime(date, '%Y%m%d') as date)  as service_date

    from source
    -- OVapi's calendar_dates.txt is a pure flat list of active dates, not a
    -- patch on top of a calendar.txt pattern: every row observed in the real
    -- feed is exception_type = 1 (added), never 2 (removed). Filtering on it
    -- anyway, rather than assuming, so a future feed that DOES use exclusions
    -- doesn't silently inflate the count.
    where exception_type = '1'

),

per_service as (

    select
        service_id,
        count(*)                     as total_service_days,
        min(service_date)            as service_start_date,
        max(service_date)            as service_end_date

    from renamed
    group by 1

),

weekly as (

    select
        service_id,
        total_service_days,
        service_start_date,
        service_end_date,

        -- calendar_dates.txt lists individual real dates, not a repeating
        -- weekly pattern, so a plain day-count isn't "days per week" — it's
        -- days across however many weeks the feed happens to span. Dividing
        -- by the span converts it to a genuine weekly rate, comparable
        -- across services regardless of how far out each one is published.
        -- greatest(...,1.0) guards a service with only one published date
        -- from dividing by ~zero weeks.
        greatest(
            date_diff('day', service_start_date, service_end_date) / 7.0,
            1.0
        )                             as span_weeks

    from per_service

)

select
    service_id,
    total_service_days,
    service_start_date,
    service_end_date,
    round(total_service_days / span_weeks, 2)  as days_per_week

from weekly
