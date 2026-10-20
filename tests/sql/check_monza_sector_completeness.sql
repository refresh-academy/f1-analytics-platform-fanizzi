-- Check sector-time completeness in the Monza 2024 warehouse snapshot.
-- The observed source data has 1,008 laps and 20 missing first-sector
-- times, all on lap 1. This test fails if those observations change.

-- DO executes an anonymous PL/pgSQL block once.
-- The two $$ markers delimit the block's text (dollar quoting).
-- They let us use single-quoted strings inside the block without
-- escaping those quotes.
DO $$

-- DECLARE introduces variables used only within this block.
-- BIGINT is the integer type returned by COUNT(*).
DECLARE
    laps_checked BIGINT;
    missing_first_sector BIGINT;
    missing_first_sector_after_lap_one BIGINT;
    missing_second_sector BIGINT;
    missing_third_sector BIGINT;

-- BEGIN starts the executable part of this PL/pgSQL block.
-- This BEGIN groups statements; it does not start a SQL transaction.
BEGIN
    -- COUNT(*) is an aggregate function that counts rows.
    -- FILTER (WHERE condition) makes one COUNT consider only the rows
    -- satisfying that condition.
    SELECT
        COUNT(*),

        -- IS NULL is a predicate: it tests whether a value is missing.
        COUNT(*) FILTER (WHERE lap.sector1_seconds IS NULL),

        -- <> means "not equal to". This count detects missing sector 1
        -- times on laps other than lap 1.
        COUNT(*) FILTER (
            WHERE lap.lap_number <> 1
              AND lap.sector1_seconds IS NULL
        ),

        COUNT(*) FILTER (WHERE lap.sector2_seconds IS NULL),
        COUNT(*) FILTER (WHERE lap.sector3_seconds IS NULL)

    -- In PL/pgSQL, SELECT ... INTO assigns the five query results
    -- to the five variables below, in the same order.
    INTO
        laps_checked,
        missing_first_sector,
        missing_first_sector_after_lap_one,
        missing_second_sector,
        missing_third_sector

    -- FROM selects the lap table. JOIN connects each lap to its session;
    -- ON states which identifiers must match.
    FROM warehouse.fact_lap AS lap
    JOIN warehouse.dim_session AS session
        ON session.session_id = lap.session_id

    -- WHERE limits the counts to this specific race.
    WHERE session.season = 2024
      AND session.event_name = 'Italian Grand Prix'
      AND session.session_name = 'Race';

    -- IF ... THEN ... END IF is a PL/pgSQL conditional block.
    -- OR makes the test fail if any expected count is different.
    IF laps_checked <> 1008
       OR missing_first_sector <> 20
       OR missing_first_sector_after_lap_one <> 0
       OR missing_second_sector <> 0
       OR missing_third_sector <> 0 THEN

        -- RAISE EXCEPTION reports an error and stops this test.
        -- Each % placeholder is replaced by the next variable listed.
        RAISE EXCEPTION
            'Sector check failed: % laps, % missing S1, % later missing S1, % missing S2, % missing S3',
            laps_checked,
            missing_first_sector,
            missing_first_sector_after_lap_one,
            missing_second_sector,
            missing_third_sector;
    END IF;

    -- Reaching this line means none of the failure conditions was true.
    -- RAISE NOTICE displays an informational message; it is not an error.
    RAISE NOTICE
        'Sector check passed: % laps; 20 first-sector times missing only on lap 1',
        laps_checked;

-- END closes the PL/pgSQL block; the delimiter below closes its text.
-- The final semicolon ends the DO command.
END
$$;
