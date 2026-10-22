-- Summarize FastF1's lap timing-quality flag for each Monza race driver.
-- False means a basic timing check was not passed; it does not by itself
-- establish that the recorded lap time is wrong or was deleted.
SELECT
    driver.full_name,
    participation.team_name,
    participation.driver_number,

    -- Count every recorded lap, regardless of its quality flag.
    COUNT(*) AS recorded_laps,

    -- FILTER counts only the laps satisfying its condition.
    COUNT(*) FILTER (
        WHERE lap.is_accurate IS TRUE
    ) AS flag_true_laps,
    COUNT(*) FILTER (
        WHERE lap.is_accurate IS FALSE
    ) AS flag_false_laps

FROM warehouse.fact_lap AS lap
JOIN warehouse.dim_session AS session
    ON session.session_id = lap.session_id
JOIN warehouse.session_driver AS participation
    ON participation.session_id = lap.session_id
   AND participation.driver_number = lap.driver_number
JOIN warehouse.dim_driver AS driver
    ON driver.driver_id = participation.driver_id

WHERE session.season = 2024
  AND session.event_name = 'Italian Grand Prix'
  AND session.session_name = 'Race'

-- Keep different drivers separate even if they have the same full name.
GROUP BY
    driver.driver_id,
    driver.full_name,
    participation.team_name,
    participation.driver_number

-- Show the drivers with the most False flags first.
ORDER BY flag_false_laps DESC, driver.full_name;
