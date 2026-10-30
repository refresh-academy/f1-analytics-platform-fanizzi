-- One row per driver in a race result source snapshot.
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.race_results (
    season INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    session_name TEXT NOT NULL,
    driver_number TEXT NOT NULL,
    result_position INTEGER NOT NULL CHECK (result_position > 0),
    -- Keep source text such as 'R' for a retired driver.
    classified_position TEXT NOT NULL CHECK (btrim(classified_position) <> ''),
    laps_completed INTEGER NOT NULL CHECK (laps_completed >= 0),
    status TEXT NOT NULL CHECK (btrim(status) <> ''),

    CONSTRAINT race_results_pkey
        PRIMARY KEY (season, event_name, session_name, driver_number),
    CONSTRAINT race_results_session_position_key
        UNIQUE (season, event_name, session_name, result_position)
);
