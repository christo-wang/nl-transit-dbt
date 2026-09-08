with source as (

    select * from {{ source('raw', 'trips') }}

),

renamed as (

    select
        trip_id,
        route_id,
        service_id,
        nullif(trip_headsign, '')  as trip_headsign

    from source

)

select * from renamed
