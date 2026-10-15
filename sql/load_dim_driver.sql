-- Load driver identities from the Monza race staging records.
-- PostgreSQL generates the internal driver_id automatically.
INSERT INTO warehouse.dim_driver AS target (
    source_driver_id,
    abbreviation,
    full_name
)
SELECT
    driver_id,
    abbreviation,
    full_name
FROM staging.drivers
WHERE season = 2024
  AND event_name = 'Italian Grand Prix'
  AND session_name = 'Race'
ON CONFLICT ON CONSTRAINT dim_driver_source_key DO UPDATE SET
    abbreviation = EXCLUDED.abbreviation,
    full_name = EXCLUDED.full_name
-- Skip the update when the stored details are already identical.
WHERE (target.abbreviation, target.full_name)
    IS DISTINCT FROM (EXCLUDED.abbreviation, EXCLUDED.full_name);
