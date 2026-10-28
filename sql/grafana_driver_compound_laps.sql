-- Count recorded stint laps by compound for each Monza 2024 driver.
-- The columns support a stacked bar chart; they do not show stint order.
SELECT
    driver.full_name AS driver,
    COALESCE(SUM(stint.recorded_laps) FILTER
        (WHERE stint.compound = 'HARD'), 0) AS "HARD",
    COALESCE(SUM(stint.recorded_laps) FILTER
        (WHERE stint.compound = 'MEDIUM'), 0) AS "MEDIUM",
    COALESCE(SUM(stint.recorded_laps) FILTER
        (WHERE stint.compound = 'SOFT'), 0) AS "SOFT"
FROM warehouse.fact_stint AS stint
JOIN warehouse.dim_session AS session
    ON session.session_id = stint.session_id
JOIN warehouse.session_driver AS participation
    ON participation.session_id = stint.session_id
   AND participation.driver_number = stint.driver_number
JOIN warehouse.dim_driver AS driver
    ON driver.driver_id = participation.driver_id
WHERE session.season = 2024
  AND session.event_name = 'Italian Grand Prix'
  AND session.session_name = 'Race'
GROUP BY stint.driver_number, driver.full_name
ORDER BY driver.full_name;
