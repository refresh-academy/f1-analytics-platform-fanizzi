-- Load race results through the existing session and driver participation.
INSERT INTO warehouse.fact_race_result AS target (
    session_id,
    driver_number,
    result_position,
    classified_position,
    laps_completed,
    status
)
SELECT
    session.session_id,
    result.driver_number,
    result.result_position,
    result.classified_position,
    result.laps_completed,
    result.status
FROM staging.race_results AS result
JOIN warehouse.dim_session AS session
    ON session.season = result.season
   AND session.event_name = result.event_name
   AND session.session_name = result.session_name
JOIN warehouse.session_driver AS participation
    ON participation.session_id = session.session_id
   AND participation.driver_number = result.driver_number
ON CONFLICT ON CONSTRAINT fact_race_result_pkey DO UPDATE SET
    result_position = EXCLUDED.result_position,
    classified_position = EXCLUDED.classified_position,
    laps_completed = EXCLUDED.laps_completed,
    status = EXCLUDED.status
WHERE (
    target.result_position, target.classified_position,
    target.laps_completed, target.status
) IS DISTINCT FROM (
    EXCLUDED.result_position, EXCLUDED.classified_position,
    EXCLUDED.laps_completed, EXCLUDED.status
);
