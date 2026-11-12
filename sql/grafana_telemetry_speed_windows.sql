-- Resolve the same replay used by the counters and original speed curve.
WITH selected_replay AS (
    SELECT replay_id
    FROM public.telemetry_events
    WHERE ${telemetry_replay:sqlstring} = 'latest'
       OR CAST(replay_id AS TEXT) = ${telemetry_replay:sqlstring}
    GROUP BY replay_id
    ORDER BY MIN(published_at) DESC, replay_id
    LIMIT 1
), replay_origin AS (
    -- Keep the horizontal origin consistent with the original speed curve.
    SELECT MIN(event_time) AS first_car_event_time
    FROM public.telemetry_events
    WHERE replay_id = (SELECT replay_id FROM selected_replay)
      AND event_type = 'car_data'
)
-- Plot each aggregate at its window end, relative to the first car sample.
-- Return only elapsed time and speeds so Auto mapping creates three Y series.
-- This panel covers the complete selected replay, independently of the time picker.
SELECT EXTRACT(EPOCH FROM (metrics.window_end - origin.first_car_event_time))
           ::DOUBLE PRECISION AS elapsed_seconds,
       metrics.avg_speed_kmh AS "Mean speed",
       metrics.min_speed_kmh AS "Minimum speed",
       metrics.max_speed_kmh AS "Maximum speed"
FROM public.telemetry_speed_5s AS metrics
CROSS JOIN replay_origin AS origin
WHERE metrics.replay_id = (SELECT replay_id FROM selected_replay)
ORDER BY metrics.window_start;
