-- Resolve the same replay used by the counters.
WITH selected_replay AS (
    SELECT replay_id
    FROM public.telemetry_events
    WHERE ${telemetry_replay:sqlstring} = 'latest'
       OR CAST(replay_id AS TEXT) = ${telemetry_replay:sqlstring}
    GROUP BY replay_id
    ORDER BY MIN(published_at) DESC, replay_id
    LIMIT 1
)
-- Measure elapsed time from the first available car sample.
SELECT EXTRACT(EPOCH FROM (event_time - MIN(event_time) OVER ()))::DOUBLE PRECISION
           AS elapsed_seconds,
       speed AS speed_kmh
FROM public.telemetry_events
WHERE replay_id = (SELECT replay_id FROM selected_replay)
  AND event_type = 'car_data'
ORDER BY event_time;
