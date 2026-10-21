-- Compare the FastF1 accuracy flag for every Monza 2024 race lap.
-- This snapshot has 1,008 laps: 927 True and 81 False.
--
-- DO executes the following anonymous PL/pgSQL block once.
-- The matching double-dollar delimiters mark the beginning and end
-- of the block's text. Keep those delimiters out of comments inside
-- the block, because PostgreSQL would interpret them as its end.
DO $$
DECLARE
    staging_count BIGINT;
    warehouse_count BIGINT;
    unmatched_count BIGINT;
    mismatched_count BIGINT;
    accurate_count BIGINT;
    not_accurate_count BIGINT;
BEGIN
    -- Limit both sides to the same session before matching lap keys.
    WITH source_laps AS (
        SELECT driver_number, lap_number, is_accurate
        FROM staging.laps
        WHERE season = 2024
          AND event_name = 'Italian Grand Prix'
          AND session_name = 'Race'
    ),
    warehouse_laps AS (
        SELECT lap.driver_number, lap.lap_number, lap.is_accurate
        FROM warehouse.fact_lap AS lap
        JOIN warehouse.dim_session AS session
            ON session.session_id = lap.session_id
        WHERE session.season = 2024
          AND session.event_name = 'Italian Grand Prix'
          AND session.session_name = 'Race'
    )
    SELECT
        COUNT(*) FILTER (WHERE source_laps.driver_number IS NOT NULL),
        COUNT(*) FILTER (WHERE warehouse_laps.driver_number IS NOT NULL),
        COUNT(*) FILTER (
            WHERE source_laps.driver_number IS NULL
               OR warehouse_laps.driver_number IS NULL
        ),
        COUNT(*) FILTER (
            WHERE source_laps.driver_number IS NOT NULL
              AND warehouse_laps.driver_number IS NOT NULL
              AND source_laps.is_accurate
                  IS DISTINCT FROM warehouse_laps.is_accurate
        ),
        COUNT(*) FILTER (WHERE warehouse_laps.is_accurate IS TRUE),
        COUNT(*) FILTER (WHERE warehouse_laps.is_accurate IS FALSE)
    INTO
        staging_count,
        warehouse_count,
        unmatched_count,
        mismatched_count,
        accurate_count,
        not_accurate_count
    FROM source_laps
    FULL OUTER JOIN warehouse_laps
        USING (driver_number, lap_number);

    -- RAISE EXCEPTION reports a failed assertion and stops this block.
    -- Each percent sign in the message receives the corresponding
    -- variable listed after the message, in the same order.
    IF staging_count <> 1008
       OR warehouse_count <> 1008
       OR unmatched_count <> 0
       OR mismatched_count <> 0
       OR accurate_count <> 927
       OR not_accurate_count <> 81 THEN
        RAISE EXCEPTION
            'Lap accuracy check failed: staging %, warehouse %, unmatched %, mismatched %, True %, False %',
            staging_count,
            warehouse_count,
            unmatched_count,
            mismatched_count,
            accurate_count,
            not_accurate_count;
    END IF;

    -- RAISE NOTICE prints a success message without stopping execution.
    -- The three percent signs receive the three values listed below.
    RAISE NOTICE
        'Lap accuracy check passed: % matched laps, % True, % False',
        warehouse_count, accurate_count, not_accurate_count;
END
$$;
