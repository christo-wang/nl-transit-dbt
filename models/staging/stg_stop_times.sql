with source as (

    select * from {{ source('raw', 'stop_times') }}

),

renamed as (

    select
        trip_id,
        stop_id,
        cast(stop_sequence as integer)  as stop_sequence,
        departure_time                  as departure_time_raw,

        -- GTFS times are elapsed time since noon minus 12h on the service day,
        -- so a trip leaving at 00:40 on the night of a Friday service is
        -- written 24:40:00 and belongs to Friday. Parsing this as a clock time
        -- throws or silently wraps to 00:40 and moves the departure to the
        -- wrong day. Seconds-since-service-start keeps it on Friday.
        (
            cast(split_part(departure_time, ':', 1) as integer) * 3600
          + cast(split_part(departure_time, ':', 2) as integer) * 60
          + cast(split_part(departure_time, ':', 3) as integer)
        )                               as departure_seconds

    from source
    where departure_time is not null
      and departure_time != ''

)

select * from renamed
