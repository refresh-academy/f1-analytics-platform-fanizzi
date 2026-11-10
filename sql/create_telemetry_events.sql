-- Store one source event per replay in the telemetry database.
CREATE TABLE IF NOT EXISTS public.telemetry_events (
    -- Preserve both the original measurement time and the replay publish time.
    event_time TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    replay_id UUID NOT NULL,
    event_id TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    source TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (event_type IN ('car_data', 'location')),
    session_key BIGINT NOT NULL,
    meeting_key BIGINT NOT NULL,
    driver_number INTEGER NOT NULL,

    -- Keep Kafka coordinates so each row can be traced to its message.
    kafka_topic TEXT NOT NULL,
    kafka_partition INTEGER NOT NULL,
    kafka_offset BIGINT NOT NULL,

    -- Each event type leaves the other type's measurement columns null.
    speed INTEGER,
    throttle INTEGER,
    brake INTEGER,
    rpm INTEGER,
    n_gear INTEGER,
    drs INTEGER,
    x INTEGER,
    y INTEGER,
    z INTEGER,

    -- Include the time partition column in the replay deduplication key.
    PRIMARY KEY (replay_id, event_time, event_id)
) WITH (
    tsdb.hypertable,
    tsdb.partition_column = 'event_time',
    tsdb.columnstore = false
);
