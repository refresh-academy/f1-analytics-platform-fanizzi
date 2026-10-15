-- Summarize the imported Monza 2024 race laps by driver.
-- The session dimension supplies the event information for each fact row.
SELECT
    s.season,
    s.event_name,
    s.session_name,
    f.driver_number,
    COUNT(*) AS recorded_laps,
    MIN(f.lap_time_seconds) AS fastest_lap_seconds
FROM warehouse.fact_lap AS f
JOIN warehouse.dim_session AS s
    ON s.session_id = f.session_id
WHERE s.season = 2024
  AND s.event_name = 'Italian Grand Prix'
  AND s.session_name = 'Race'
GROUP BY
    s.season,
    s.event_name,
    s.session_name,
    f.driver_number
ORDER BY fastest_lap_seconds, f.driver_number;
