-- Compare classified race positions, not individual lap times.
-- Use ClassifiedPosition so a retired driver's result order is not
-- mistaken for a classified finishing position.
SELECT
    CASE
        WHEN result.classified_position = '1'
            THEN driver.full_name || ' (winner)'
        ELSE driver.full_name
    END AS driver,
    result.classified_position::integer AS finishing_position
FROM warehouse.fact_race_result AS result
JOIN warehouse.dim_session AS session
    ON session.session_id = result.session_id
JOIN warehouse.session_driver AS participation
    ON participation.session_id = result.session_id
   AND participation.driver_number = result.driver_number
JOIN warehouse.dim_driver AS driver
    ON driver.driver_id = participation.driver_id
WHERE session.season = 2024
  AND session.event_name = 'Italian Grand Prix'
  AND session.session_name = 'Race'
  AND result.driver_number IN ('16', '44')
  AND result.classified_position ~ '^[0-9]+$'
ORDER BY finishing_position;
