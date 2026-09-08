with source as (

    select * from {{ source('raw', 'stops') }}

),

renamed as (

    select
        stop_id,
        stop_name,
        cast(stop_lat as double)                      as stop_latitude,
        cast(stop_lon as double)                      as stop_longitude,
        coalesce(nullif(location_type, ''), '0')      as location_type,
        nullif(parent_station, '')                    as parent_station_id

    from source

)

select * from renamed
-- location_type 0 is a boarding location. 1 is a station, 2 an entrance, and
-- so on; those are containers, not places a vehicle stops, so counting
-- departures against them would double-count.
where location_type = '0'
