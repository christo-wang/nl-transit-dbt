with source as (

    select * from {{ source('raw', 'calendar') }}

),

renamed as (

    select
        service_id,

        -- days_per_week turns a service pattern into a weight. A Sunday-only
        -- service contributes one day of running per week, a weekday service
        -- five. Without this, summing departures across service patterns
        -- counts a Sunday trip as heavily as a weekday one.
        cast(monday    as integer)
      + cast(tuesday   as integer)
      + cast(wednesday as integer)
      + cast(thursday  as integer)
      + cast(friday    as integer)
      + cast(saturday  as integer)
      + cast(sunday    as integer)     as days_per_week,

        cast(strptime(start_date, '%Y%m%d') as date)  as service_start_date,
        cast(strptime(end_date, '%Y%m%d') as date)    as service_end_date

    from source

)

select * from renamed
