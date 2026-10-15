-- Connect each Monza driver to the session, race number, and team.
INSERT INTO warehouse.session_driver AS target (
    session_id,
    driver_id,
    driver_number,
    team_name
)
SELECT
    session.session_id,
    driver.driver_id,
    staged.driver_number,
    staged.team_name
FROM staging.drivers AS staged
JOIN warehouse.dim_session AS session
    ON session.season = staged.season
   AND session.event_name = staged.event_name
   AND session.session_name = staged.session_name
JOIN warehouse.dim_driver AS driver
    ON driver.source_driver_id = staged.driver_id
WHERE staged.season = 2024
  AND staged.event_name = 'Italian Grand Prix'
  AND staged.session_name = 'Race'
ON CONFLICT ON CONSTRAINT session_driver_pkey DO UPDATE SET
    driver_id = EXCLUDED.driver_id,
    team_name = EXCLUDED.team_name
-- Preserve unchanged rows on repeated loads.
WHERE (target.driver_id, target.team_name)
    IS DISTINCT FROM (EXCLUDED.driver_id, EXCLUDED.team_name);
