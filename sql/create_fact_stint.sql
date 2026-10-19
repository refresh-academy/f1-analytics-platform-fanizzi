-- One row represents one driver's stint in one session.
CREATE TABLE IF NOT EXISTS warehouse.fact_stint (
    session_id BIGINT NOT NULL,
    driver_number TEXT NOT NULL,
    stint_number INTEGER NOT NULL CHECK (stint_number > 0),
    compound TEXT NOT NULL CHECK (btrim(compound) <> ''),
    recorded_laps INTEGER NOT NULL CHECK (recorded_laps > 0),
    first_lap INTEGER NOT NULL CHECK (first_lap > 0),
    last_lap INTEGER NOT NULL,

    -- A driver cannot have the same stint number twice in a session.
    CONSTRAINT fact_stint_pkey
        PRIMARY KEY (session_id, driver_number, stint_number),

    -- Associate the stint with a driver participating in this session.
    CONSTRAINT fact_stint_driver_fkey
        FOREIGN KEY (session_id, driver_number)
        REFERENCES warehouse.session_driver (session_id, driver_number),

    -- The current source data has continuous lap ranges within each stint.
    CONSTRAINT fact_stint_lap_range_check
        CHECK (last_lap >= first_lap),
    CONSTRAINT fact_stint_lap_count_matches_range_check
        CHECK (recorded_laps = last_lap - first_lap + 1)
);
