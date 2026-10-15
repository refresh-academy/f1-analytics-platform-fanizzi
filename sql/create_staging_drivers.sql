-- Staging keeps driver details tied to the session they came from.
CREATE SCHEMA IF NOT EXISTS staging;

CREATE TABLE IF NOT EXISTS staging.drivers (
    season INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    session_name TEXT NOT NULL,
    driver_number TEXT NOT NULL,
    driver_id TEXT NOT NULL,
    abbreviation TEXT NOT NULL,
    full_name TEXT NOT NULL,
    team_name TEXT NOT NULL,

    -- A race number identifies one driver within this session.
    CONSTRAINT drivers_pkey PRIMARY KEY (
        season, event_name, session_name, driver_number
    ),

    -- The source driver ID must also appear only once in this session.
    CONSTRAINT drivers_session_driver_id_key UNIQUE (
        season, event_name, session_name, driver_id
    )
);
