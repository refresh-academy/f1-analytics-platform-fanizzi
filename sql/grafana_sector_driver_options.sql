-- List the Monza 2024 race drivers for Grafana's two selectors.
-- Grafana displays __text in the menu and passes __value to panel queries.
-- Show the eligible lap count so a five-lap sample is easy to recognize.
SELECT
    format(
        '%s (%s usable laps)',
        driver.full_name,
        COUNT(*) FILTER (
            WHERE lap.is_accurate
              AND lap.sector1_seconds IS NOT NULL
              AND lap.sector2_seconds IS NOT NULL
              AND lap.sector3_seconds IS NOT NULL
        )
    ) AS __text,
    lap.driver_number AS __value
FROM warehouse.fact_lap AS lap
-- Identify the race before grouping its driver records.
JOIN warehouse.dim_session AS session
    ON session.session_id = lap.session_id
-- The race number connects each lap to that driver's participation.
JOIN warehouse.session_driver AS participation
    ON participation.session_id = lap.session_id
   AND participation.driver_number = lap.driver_number
JOIN warehouse.dim_driver AS driver
    ON driver.driver_id = participation.driver_id
WHERE session.season = 2024
  AND session.event_name = 'Italian Grand Prix'
  AND session.session_name = 'Race'
-- One menu entry per driver; COUNT considers that driver's laps.
GROUP BY driver.full_name, lap.driver_number
ORDER BY driver.full_name;
