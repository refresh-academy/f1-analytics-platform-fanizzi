-- Compare recorded lap times for Leclerc (#16) and Piastri (#81), Monza 2024.
-- IsAccurate=True is a basic FastF1 timing check, not official validation.
-- Keep every lap number; NULL means no included time for that driver/lap.
SELECT
    lap.lap_number,
    MAX(lap.lap_time_seconds) FILTER
        (WHERE lap.driver_number = '16' AND lap.is_accurate)
        AS "Charles Leclerc (s)",
    MAX(lap.lap_time_seconds) FILTER
        (WHERE lap.driver_number = '81' AND lap.is_accurate)
        AS "Oscar Piastri (s)"
FROM warehouse.fact_lap AS lap
JOIN warehouse.dim_session AS session
    ON session.session_id = lap.session_id
WHERE session.season = 2024
  AND session.event_name = 'Italian Grand Prix'
  AND session.session_name = 'Race'
  AND lap.driver_number IN ('16', '81')
GROUP BY lap.lap_number
ORDER BY lap.lap_number;
