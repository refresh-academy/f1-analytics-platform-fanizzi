-- Store the latest Spark result for each five-second event-time window.
-- One row belongs to one replay, session, driver, and window start.
CREATE TABLE IF NOT EXISTS public.telemetry_speed_5s (
    -- Use the historical measurement time, not the replay publication time.
    -- The start is included and the end is excluded: [window_start, window_end).
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    replay_id UUID NOT NULL,
    session_key BIGINT NOT NULL,
    driver_number INTEGER NOT NULL,

    -- Count only car telemetry events that contain a valid speed value.
    -- Position events do not contain speed and do not contribute here.
    sample_count BIGINT NOT NULL CHECK (sample_count > 0),

    -- Store the arithmetic mean of sampled speeds, in kilometres per hour.
    -- This is a sample mean, not a time-weighted mean or a whole-lap average.
    avg_speed_kmh DOUBLE PRECISION NOT NULL,
    min_speed_kmh INTEGER NOT NULL CHECK (min_speed_kmh >= 0),
    max_speed_kmh INTEGER NOT NULL,

    -- The writer must refresh this field whenever an aggregate changes.
    -- It records the database write time, not event time or publication time.
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Spark may update a window as more samples arrive in later micro-batches.
    -- The writer will replace its aggregate values using this stable key.
    -- Include window_start because it is also the hypertable partition column.
    PRIMARY KEY (replay_id, session_key, driver_number, window_start),

    -- Reject intervals that do not match this table's fixed five-second grain.
    CONSTRAINT telemetry_speed_5s_window_width
        CHECK (window_end = window_start + INTERVAL '5 seconds'),

    -- Keep the mean within the observed minimum and maximum speed.
    CONSTRAINT telemetry_speed_5s_speed_bounds
        CHECK (min_speed_kmh <= avg_speed_kmh AND avg_speed_kmh <= max_speed_kmh)
) WITH (
    tsdb.hypertable,
    tsdb.partition_column = 'window_start',
    -- Keep rows in the rowstore for repeated aggregate updates during a replay.
    tsdb.columnstore = false
);

COMMENT ON TABLE public.telemetry_speed_5s IS
    'Latest Spark aggregates for five-second event-time windows per replay, session, and driver.';
