with source as (

    select * from {{ source('raw', 'routes') }}

),

renamed as (

    select
        route_id,
        route_short_name,
        route_long_name,

        case cast(route_type as integer)
            when 2 then 'rail'
            when 3 then 'bus'
            else 'other'
        end as route_category

    from source

)

select * from renamed
