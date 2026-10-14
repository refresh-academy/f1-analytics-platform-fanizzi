-- Analytical tables live separately from imported staging data.
CREATE SCHEMA IF NOT EXISTS warehouse;

-- One row represents one session of one event in one season.
CREATE TABLE IF NOT EXISTS warehouse.dim_session (
    session_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    season INTEGER NOT NULL,
    event_name TEXT NOT NULL,
    session_name TEXT NOT NULL,

    -- Prevent two identifiers for the same real-world session.
    CONSTRAINT dim_session_business_key
        UNIQUE (season, event_name, session_name)
);
