-- Link a driver identity to one session, race number, and team.
CREATE TABLE IF NOT EXISTS warehouse.session_driver (
    session_id BIGINT NOT NULL,
    driver_id BIGINT NOT NULL,
    driver_number TEXT NOT NULL,
    team_name TEXT NOT NULL,

    -- One race number belongs to one driver in a session.
    CONSTRAINT session_driver_pkey
        PRIMARY KEY (session_id, driver_number),

    -- The same driver appears only once in a session.
    CONSTRAINT session_driver_session_identity_key
        UNIQUE (session_id, driver_id),

    CONSTRAINT session_driver_session_fkey
        FOREIGN KEY (session_id)
        REFERENCES warehouse.dim_session (session_id),

    CONSTRAINT session_driver_driver_fkey
        FOREIGN KEY (driver_id)
        REFERENCES warehouse.dim_driver (driver_id),

    CONSTRAINT session_driver_number_not_blank
        CHECK (btrim(driver_number) <> ''),

    CONSTRAINT session_driver_team_not_blank
        CHECK (btrim(team_name) <> '')
);
