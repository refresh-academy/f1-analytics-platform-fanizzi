-- Receive the processed stint records before loading the warehouse.
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.stints (
    -- These fields identify the source session.
    season INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    session_name TEXT NOT NULL,

    -- A stint number is meaningful within one driver's session.
    driver_number TEXT NOT NULL,
    stint_number INTEGER NOT NULL CHECK (stint_number > 0),

    -- The compound describes the stint; it does not identify it.
    compound TEXT NOT NULL,
    recorded_laps INTEGER NOT NULL CHECK (recorded_laps > 0),
    first_lap INTEGER NOT NULL CHECK (first_lap > 0),
    last_lap INTEGER NOT NULL,

    -- Prevent loading the same stint more than once.
    CONSTRAINT stints_pkey PRIMARY KEY (
        season, event_name, session_name, driver_number, stint_number
    ),

    -- A stint cannot finish before its first recorded lap.
    CONSTRAINT stints_lap_range_check
        CHECK (last_lap >= first_lap),

    -- Our validated input contains continuous lap ranges.
    -- For example, laps 13 through 35 contain 23 recorded laps.
    -- Use a distinct name from the automatically named positive-count check.
    CONSTRAINT stints_lap_count_matches_range_check
        CHECK (recorded_laps = last_lap - first_lap + 1)
);
