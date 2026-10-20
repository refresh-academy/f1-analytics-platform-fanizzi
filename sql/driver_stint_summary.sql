-- Explore the stints recorded for each driver in the 2024 Monza race.
-- The team comes from session participation because it belongs to this race.
SELECT
    driver.full_name,
    participation.team_name,
    stint.driver_number,
    stint.stint_number,
    stint.compound,
    stint.first_lap,
    stint.last_lap,
    stint.recorded_laps
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
ORDER BY driver.full_name, stint.stint_number;
