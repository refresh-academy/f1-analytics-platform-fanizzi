-- Check that recorded lap time agrees with the sum of three sector times.
-- Only laps with all three sectors available can be checked.
-- Allow differences up to 0.01 seconds (10 milliseconds).
DO $$
DECLARE
    complete_laps_checked BIGINT;
    differences_over_10_ms BIGINT;
BEGIN
    WITH complete_laps AS (
        SELECT
            ABS(
                lap.lap_time_seconds
                - lap.sector1_seconds
                - lap.sector2_seconds
                - lap.sector3_seconds
            ) AS difference_seconds
        FROM warehouse.fact_lap AS lap
        JOIN warehouse.dim_session AS session
            ON session.session_id = lap.session_id
        WHERE session.season = 2024
          AND session.event_name = 'Italian Grand Prix'
          AND session.session_name = 'Race'
          AND lap.sector1_seconds IS NOT NULL
          AND lap.sector2_seconds IS NOT NULL
          AND lap.sector3_seconds IS NOT NULL
    )
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE difference_seconds > 0.01)
    INTO complete_laps_checked, differences_over_10_ms
    FROM complete_laps;

    -- The expected number describes this Monza source snapshot.
    -- Any larger difference means the sector sum needs investigation.
    IF complete_laps_checked <> 988 OR differences_over_10_ms <> 0 THEN
        RAISE EXCEPTION
            'Sector sum check failed: % complete laps, % differences over 10 ms',
            complete_laps_checked, differences_over_10_ms;
    END IF;

    RAISE NOTICE
        'Sector sum check passed: % complete laps, % differences over 10 ms',
        complete_laps_checked, differences_over_10_ms;
END
$$;
