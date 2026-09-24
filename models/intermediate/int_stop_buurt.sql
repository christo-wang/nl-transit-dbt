with stops as (

    select * from {{ ref('stg_stops') }}

),

buurten as (

    select * from {{ ref('stg_buurten') }}

),

stops_transformed as (

    select
        stop_id,
        stop_name,

        -- stg_stops carries WGS84 degrees (GTFS's native format). stg_buurten
        -- carries EPSG:28992 metres (CBS's native format). A raw ST_Point
        -- built from stop_latitude/stop_longitude would compare degrees
        -- against metres, so ST_Transform reprojects it into the polygons'
        -- CRS before anything is compared.
        --
        -- The catch: EPSG:4326's *official* axis order is (latitude,
        -- longitude) -- backwards from the (x, y) = (longitude, latitude)
        -- order almost every GIS tool actually writes points in, including
        -- the ST_Point(stop_longitude, stop_latitude) call below. Passing
        -- source_crs/target_crs to ST_Transform makes it enforce that
        -- official axis order, so it silently read our (lon, lat) point as
        -- (lat, lon) and reprojected it to a coordinate roughly 1,300km from
        -- where the stop actually is -- nowhere near any Dutch buurt, hence
        -- zero ST_Within matches with no error anywhere. always_xy := true
        -- tells it "trust the order I gave you (x, y)", which is what we want.
        ST_Transform(
            ST_Point(stop_longitude, stop_latitude),
            'EPSG:4326',
            'EPSG:28992',
            always_xy := true
        )  as stop_point_rd

    from stops

),

joined as (

    select
        stops_transformed.stop_id,
        stops_transformed.stop_name,
        buurten.buurtcode,
        buurten.buurtnaam,
        buurten.wijkcode,
        buurten.gemeentecode,
        buurten.gemeentenaam

    from stops_transformed
    inner join buurten
        on ST_Within(stops_transformed.stop_point_rd, buurten.geometry)

)

select * from joined
