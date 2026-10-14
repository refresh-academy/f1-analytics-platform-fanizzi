-- Derive one session row from the lap records already loaded into staging.
INSERT INTO warehouse.dim_session (season, event_name, session_name)
SELECT season, event_name, session_name
FROM staging.laps
GROUP BY season, event_name, session_name
ON CONFLICT ON CONSTRAINT dim_session_business_key DO NOTHING;
