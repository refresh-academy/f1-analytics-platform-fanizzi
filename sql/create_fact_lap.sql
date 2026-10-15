-- One row represents one driver's lap in one session.
CREATE TABLE IF NOT EXISTS warehouse.fact_lap (
    session_id BIGINT NOT NULL,
    driver_number TEXT NOT NULL,
    lap_number INTEGER NOT NULL CHECK (lap_number > 0),
    lap_time_seconds DOUBLE PRECISION NOT NULL CHECK (lap_time_seconds > 0),
    sector1_seconds DOUBLE PRECISION,
    sector2_seconds DOUBLE PRECISION,
    sector3_seconds DOUBLE PRECISION,
    compound TEXT NOT NULL,

    -- Prevent duplicate laps within the same session.
    CONSTRAINT fact_lap_pkey
        PRIMARY KEY (session_id, driver_number, lap_number),

    -- Every analytical lap must belong to a known session.
    CONSTRAINT fact_lap_session_fkey
        FOREIGN KEY (session_id) REFERENCES warehouse.dim_session (session_id)
);
