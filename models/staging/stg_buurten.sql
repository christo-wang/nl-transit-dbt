with source as (

    select * from {{ source('buurten_raw', 'buurten') }}

),

renamed as (

    select
        buurtcode,
        buurtnaam,
        wijkcode,
        gemeentecode,
        gemeentenaam,
        aantal_inwoners,

        -- Loaded as WKB bytes (ingest/load_buurten.py used geopandas, not
        -- DuckDB's own GeoPackage reader, to route around an unreachable
        -- extension-download server in some environments). ST_GeomFromWKB
        -- reconstitutes a real GEOMETRY value from those bytes — no
        -- information is lost, this is just where the conversion happens.
        -- The source CRS is EPSG:28992 (Rijksdriehoeksmeting, metres) — NOT
        -- WGS84 degrees, which is what GTFS stop coordinates use. Every
        -- spatial join against stg_stops must ST_Transform one side to
        -- match the other, or every match silently fails.
        ST_SetCRS(ST_GeomFromWKB(geometry), 'EPSG:28992')  as geometry

    from source

    -- CBS uses aantal_inwoners = -99997 as a sentinel for polygons that
    -- aren't real neighbourhoods: large water bodies ("Groot binnenwater")
    -- and a catch-all "Buitenland" (abroad) row. A negative population is
    -- never legitimate, so this excludes both without hard-coding names.
    where aantal_inwoners >= 0

)

select * from renamed
