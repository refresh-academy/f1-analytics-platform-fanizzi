-- Move processed stints from staging into the warehouse.
-- Staging stores the session's business fields; the warehouse uses session_id.
INSERT INTO warehouse.fact_stint AS target (
    session_id,
    driver_number,
    stint_number,
    compound,
    recorded_laps,
    first_lap,
    last_lap
)
SELECT
    s.session_id,
    st.driver_number,
    st.stint_number,
    st.compound,
    st.recorded_laps,
    st.first_lap,
    st.last_lap
FROM staging.stints AS st
JOIN warehouse.dim_session AS s
    ON s.season = st.season
   AND s.event_name = st.event_name
   AND s.session_name = st.session_name

-- The primary key identifies an existing stint during a repeated load.
ON CONFLICT ON CONSTRAINT fact_stint_pkey DO UPDATE
SET
    compound = EXCLUDED.compound,
    recorded_laps = EXCLUDED.recorded_laps,
    first_lap = EXCLUDED.first_lap,
    last_lap = EXCLUDED.last_lap

-- Update only when at least one stored value differs.
-- IS DISTINCT FROM also handles comparisons involving NULL safely.
WHERE (
    target.compound,
    target.recorded_laps,
    target.first_lap,
    target.last_lap
) IS DISTINCT FROM (
    EXCLUDED.compound,
    EXCLUDED.recorded_laps,
    EXCLUDED.first_lap,
    EXCLUDED.last_lap
);
