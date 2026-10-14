-- Keep imported lap data separate from the analytical warehouse tables.
CREATE SCHEMA IF NOT EXISTS staging;

-- One row represents one driver's lap in one session.
CREATE TABLE IF NOT EXISTS staging.laps (
    season INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    session_name TEXT NOT NULL,
    driver_number TEXT NOT NULL,
    lap_number INTEGER NOT NULL CHECK (lap_number > 0),
    lap_time_seconds DOUBLE PRECISION NOT NULL CHECK (lap_time_seconds > 0),
    sector1_seconds DOUBLE PRECISION,
    sector2_seconds DOUBLE PRECISION,
    sector3_seconds DOUBLE PRECISION,
    compound TEXT NOT NULL,

    -- The same driver cannot have the same lap twice in one session.
    CONSTRAINT laps_pkey PRIMARY KEY (
        season, event_name, session_name, driver_number, lap_number
    )
);
