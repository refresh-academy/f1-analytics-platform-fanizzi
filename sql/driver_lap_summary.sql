-- Summarize the imported Monza 2024 race laps by driver.
-- Join session participation to show the driver's name and team for this race.
-- The minimum recorded lap time is exploratory, not an official fastest-lap result.
SELECT
    s.season,
    s.event_name,
    s.session_name,
    f.driver_number,
    d.full_name,
    sd.team_name,
    COUNT(*) AS recorded_laps,
    MIN(f.lap_time_seconds) AS minimum_recorded_lap_seconds
FROM warehouse.fact_lap AS f
JOIN warehouse.dim_session AS s
    ON s.session_id = f.session_id
JOIN warehouse.session_driver AS sd
    ON sd.session_id = f.session_id
   AND sd.driver_number = f.driver_number
JOIN warehouse.dim_driver AS d
    ON d.driver_id = sd.driver_id
WHERE s.season = 2024
  AND s.event_name = 'Italian Grand Prix'
  AND s.session_name = 'Race'
GROUP BY
    s.season,
    s.event_name,
    s.session_name,
    f.driver_number,
    d.full_name,
    sd.team_name
ORDER BY minimum_recorded_lap_seconds, f.driver_number;
