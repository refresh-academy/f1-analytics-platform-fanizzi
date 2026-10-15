-- Store one row for each driver identity found in the source data.
CREATE SCHEMA IF NOT EXISTS warehouse;

CREATE TABLE IF NOT EXISTS warehouse.dim_driver (
    -- Internal key used by other warehouse tables.
    driver_id BIGINT GENERATED ALWAYS AS IDENTITY,
    source_driver_id TEXT NOT NULL,
    abbreviation TEXT NOT NULL,
    full_name TEXT NOT NULL,

    CONSTRAINT dim_driver_pkey PRIMARY KEY (driver_id),

    -- The same FastF1 driver identity must not be loaded twice.
    CONSTRAINT dim_driver_source_key UNIQUE (source_driver_id),

    CONSTRAINT dim_driver_source_id_not_blank
        CHECK (btrim(source_driver_id) <> '')
);
