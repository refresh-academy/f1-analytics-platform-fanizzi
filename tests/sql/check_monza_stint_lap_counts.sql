-- For each Monza 2024 driver, compare recorded lap rows with the
-- number of laps represented by that driver's warehouse stints.
-- Raise an error so a failed check also makes psql exit unsuccessfully.
DO $$
DECLARE
    drivers_checked BIGINT;
    mismatched_drivers BIGINT;
BEGIN
    WITH target_session AS (
        SELECT session_id
        FROM warehouse.dim_session
        WHERE season = 2024
          AND event_name = 'Italian Grand Prix'
          AND session_name = 'Race'
    ),
    lap_totals AS (
        SELECT lap.driver_number, COUNT(*) AS lap_count
        FROM warehouse.fact_lap AS lap
        JOIN target_session AS session
            ON session.session_id = lap.session_id
        GROUP BY lap.driver_number
    ),
    stint_totals AS (
        SELECT stint.driver_number, SUM(stint.recorded_laps) AS stint_laps
        FROM warehouse.fact_stint AS stint
        JOIN target_session AS session
            ON session.session_id = stint.session_id
        GROUP BY stint.driver_number
    )
    SELECT
        COUNT(*),
        COUNT(*) FILTER (
            WHERE lap.lap_count IS DISTINCT FROM stint.stint_laps
        )
    INTO drivers_checked, mismatched_drivers
    FROM lap_totals AS lap
    FULL JOIN stint_totals AS stint
        ON stint.driver_number = lap.driver_number;

    IF drivers_checked <> 20 OR mismatched_drivers <> 0 THEN
        RAISE EXCEPTION
            'Stint/lap check failed: % drivers checked, % mismatched',
            drivers_checked, mismatched_drivers;
    END IF;

    RAISE NOTICE
        'Stint/lap check passed: % drivers matched',
        drivers_checked;
END
$$;
