-- One row represents one driver's result in one race session.
CREATE TABLE IF NOT EXISTS warehouse.fact_race_result (
    session_id BIGINT NOT NULL,
    driver_number TEXT NOT NULL,
    -- Source Position orders results; it does not imply classification.
    result_position INTEGER NOT NULL CHECK (result_position > 0),
    -- Preserve source values such as 'R' for a retired driver.
    classified_position TEXT NOT NULL CHECK (btrim(classified_position) <> ''),
    laps_completed INTEGER NOT NULL CHECK (laps_completed >= 0),
    status TEXT NOT NULL CHECK (btrim(status) <> ''),

    CONSTRAINT fact_race_result_pkey
        PRIMARY KEY (session_id, driver_number),
    CONSTRAINT fact_race_result_session_position_key
        UNIQUE (session_id, result_position),
    CONSTRAINT fact_race_result_driver_fkey
        FOREIGN KEY (session_id, driver_number)
        REFERENCES warehouse.session_driver (session_id, driver_number)
);
