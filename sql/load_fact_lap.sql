-- Move validated lap data from staging into the analytical fact table.
-- One fact row represents one driver's lap in one session.
INSERT INTO warehouse.fact_lap (
    session_id,
    driver_number,
    lap_number,
    lap_time_seconds,
    sector1_seconds,
    sector2_seconds,
    sector3_seconds,
    compound,
    is_accurate
)
SELECT
    -- Store the session's identifier instead of repeating its descriptive fields.
    s.session_id,
    l.driver_number,
    l.lap_number,
    l.lap_time_seconds,
    l.sector1_seconds,
    l.sector2_seconds,
    l.sector3_seconds,
    l.compound,
    l.is_accurate
FROM staging.laps AS l
JOIN warehouse.dim_session AS s
    -- These three source fields identify the corresponding dimension row.
    ON s.season = l.season
   AND s.event_name = l.event_name
   AND s.session_name = l.session_name

-- The primary key identifies a lap by session, driver, and lap number.
-- A conflict means that this lap already exists in the fact table.
ON CONFLICT ON CONSTRAINT fact_lap_pkey DO UPDATE SET
    -- EXCLUDED contains the incoming values proposed by the SELECT above.
    lap_time_seconds = EXCLUDED.lap_time_seconds,
    sector1_seconds = EXCLUDED.sector1_seconds,
    sector2_seconds = EXCLUDED.sector2_seconds,
    sector3_seconds = EXCLUDED.sector3_seconds,
    compound = EXCLUDED.compound,
    is_accurate = EXCLUDED.is_accurate

-- Update only if a measurement, compound, or quality flag changed.
-- IS DISTINCT FROM treats NULL versus NULL as unchanged.
WHERE (
    fact_lap.lap_time_seconds,
    fact_lap.sector1_seconds,
    fact_lap.sector2_seconds,
    fact_lap.sector3_seconds,
    fact_lap.compound,
    fact_lap.is_accurate
) IS DISTINCT FROM (
    EXCLUDED.lap_time_seconds,
    EXCLUDED.sector1_seconds,
    EXCLUDED.sector2_seconds,
    EXCLUDED.sector3_seconds,
    EXCLUDED.compound,
    EXCLUDED.is_accurate
);
