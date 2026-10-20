-- Check each warehouse lap against the recorded stint ranges.
-- A lap must belong to exactly one stint for its driver and session,
-- and its compound must agree with that stint.
DO $$
DECLARE
    laps_checked BIGINT;
    range_errors BIGINT;
    compound_errors BIGINT;
BEGIN
    WITH lap_checks AS (
        SELECT
            lap.session_id,
            lap.driver_number,
            lap.lap_number,

            -- Zero means no stint covers the lap; more than one means
            -- that two stint ranges overlap at this lap.
            COUNT(stint.stint_number) AS matching_ranges,

            -- Count covering stints with the same compound as the lap.
            COUNT(stint.stint_number) FILTER (
                WHERE stint.compound = lap.compound
            ) AS matching_compounds
        FROM warehouse.fact_lap AS lap
        JOIN warehouse.dim_session AS session
            ON session.session_id = lap.session_id
        LEFT JOIN warehouse.fact_stint AS stint
            ON stint.session_id = lap.session_id
           AND stint.driver_number = lap.driver_number
           AND lap.lap_number BETWEEN stint.first_lap AND stint.last_lap
        WHERE session.season = 2024
          AND session.event_name = 'Italian Grand Prix'
          AND session.session_name = 'Race'
        GROUP BY lap.session_id, lap.driver_number, lap.lap_number
    )
    SELECT
        COUNT(*),
        COUNT(*) FILTER (WHERE matching_ranges <> 1),
        COUNT(*) FILTER (
            WHERE matching_ranges = 1 AND matching_compounds <> 1
        )
    INTO laps_checked, range_errors, compound_errors
    FROM lap_checks;

    IF laps_checked <> 1008 OR range_errors <> 0 OR compound_errors <> 0 THEN
        RAISE EXCEPTION
            'Stint assignment check failed: % laps, % range errors, % compound errors',
            laps_checked, range_errors, compound_errors;
    END IF;

    RAISE NOTICE
        'Stint assignment check passed: % laps, % range errors, % compound errors',
        laps_checked, range_errors, compound_errors;
END
$$;
