-- Offer automatic selection of the newest replay and explicit past replays.
-- Grafana displays __text and passes __value to the panel queries.
WITH replays AS (
    SELECT replay_id, MIN(published_at) AS started_at
    FROM public.telemetry_events
    GROUP BY replay_id
)
SELECT __text, __value
FROM (
    -- Keep the live demo's automatic selection at the top of the menu.
    SELECT 'Latest replay (auto)'::TEXT AS __text,
           'latest'::TEXT AS __value,
           0 AS option_group,
           NULL::TIMESTAMPTZ AS started_at
    UNION ALL
    SELECT format(
               '%s UTC | %s',
               to_char(started_at AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
               replay_id
           ),
           replay_id::TEXT,
           1,
           started_at
    FROM replays
) AS options
ORDER BY option_group, started_at DESC, __value;
