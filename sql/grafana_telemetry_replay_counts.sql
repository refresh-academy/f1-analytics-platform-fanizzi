-- Resolve the automatic choice or the explicit replay selected in Grafana.
WITH selected_replay AS (
    SELECT replay_id
    FROM public.telemetry_events
    WHERE ${telemetry_replay:sqlstring} = 'latest'
       OR CAST(replay_id AS TEXT) = ${telemetry_replay:sqlstring}
    GROUP BY replay_id
    ORDER BY MIN(published_at) DESC, replay_id
    LIMIT 1
)
SELECT COUNT(*) AS "Total events",
       COUNT(*) FILTER (WHERE event_type = 'car_data') AS "Car telemetry events",
       COUNT(*) FILTER (WHERE event_type = 'location') AS "Position events"
FROM public.telemetry_events
WHERE replay_id = (SELECT replay_id FROM selected_replay);
