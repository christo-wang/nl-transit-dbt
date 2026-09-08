-- ============================================================================
-- service_level.sql
-- Handed over 2024. Original author no longer with the team.
-- Run manually against the GTFS extract. Output feeds the service-level report.
-- No tests. No documentation beyond this header.
-- ============================================================================

CREATE OR REPLACE TABLE legacy_service_level AS
SELECT
    s.stop_id,
    s.stop_name,
    COUNT(*) AS departures_per_week
FROM raw.stop_times st
JOIN raw.trips t   ON st.trip_id = t.trip_id
JOIN raw.stops s   ON st.stop_id = s.stop_id
JOIN raw.calendar c ON t.service_id = c.service_id
WHERE st.departure_time IS NOT NULL
GROUP BY 1, 2;
