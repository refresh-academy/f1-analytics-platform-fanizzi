-- Compare Spark metrics with an independent calculation from stored raw events.
-- Run with psql --single-transaction -v replay_id=UUID -f this_file.sql.
-- Keep intermediate comparison results only for the current transaction.
CREATE TEMP TABLE speed_window_comparison ON COMMIT DROP AS
WITH expected AS (
    SELECT replay_id,
           session_key,
           driver_number,
           -- Match Spark's five-second windows aligned to the Unix epoch.
           date_bin(
               INTERVAL '5 seconds', event_time,
               TIMESTAMPTZ '1970-01-01 00:00:00+00'
           ) AS window_start,
           COUNT(*) AS sample_count,
           AVG(speed)::DOUBLE PRECISION AS avg_speed_kmh,
           MIN(speed) AS min_speed_kmh,
           MAX(speed) AS max_speed_kmh
    FROM public.telemetry_events
    WHERE replay_id = :'replay_id'::uuid
      AND event_type = 'car_data'
      AND speed IS NOT NULL
    GROUP BY 1, 2, 3, 4
), actual AS (
    SELECT *
    FROM public.telemetry_speed_5s
    WHERE replay_id = :'replay_id'::uuid
)
SELECT replay_id,
       session_key,
       driver_number,
       window_start,
       expected.sample_count AS expected_samples,
       actual.sample_count AS stored_samples,
       (
           -- The full join also detects missing and unexpected windows.
           expected.sample_count IS NULL
           OR actual.sample_count IS NULL
           OR actual.window_end IS DISTINCT FROM
               expected.window_start + INTERVAL '5 seconds'
           OR actual.sample_count IS DISTINCT FROM expected.sample_count
           OR actual.min_speed_kmh IS DISTINCT FROM expected.min_speed_kmh
           OR actual.max_speed_kmh IS DISTINCT FROM expected.max_speed_kmh
           -- Allow only a tiny floating-point difference in the sample mean.
           OR ABS(actual.avg_speed_kmh - expected.avg_speed_kmh) > 1e-9
       ) AS mismatch
FROM expected
FULL OUTER JOIN actual
USING (replay_id, session_key, driver_number, window_start);

SELECT COUNT(*) FILTER (WHERE expected_samples IS NOT NULL) AS expected_windows,
       COUNT(*) FILTER (WHERE stored_samples IS NOT NULL) AS stored_windows,
       COALESCE(SUM(expected_samples), 0)::BIGINT AS expected_samples,
       COALESCE(SUM(stored_samples), 0)::BIGINT AS stored_samples,
       COUNT(*) FILTER (WHERE mismatch) AS mismatched_windows
FROM speed_window_comparison;

-- An empty source or a disagreement must fail the command, not just print rows.
DO $$
DECLARE
    expected_count BIGINT;
    mismatch_count BIGINT;
BEGIN
    SELECT COUNT(*) FILTER (WHERE expected_samples IS NOT NULL),
           COUNT(*) FILTER (WHERE mismatch)
    INTO expected_count, mismatch_count
    FROM speed_window_comparison;

    IF expected_count = 0 THEN
        RAISE EXCEPTION 'No raw speed samples found for the selected replay.';
    END IF;

    IF mismatch_count > 0 THEN
        RAISE EXCEPTION
            'Speed-window validation failed: % mismatched windows.', mismatch_count;
    END IF;

    RAISE NOTICE 'Speed-window validation passed.';
END;
$$;
