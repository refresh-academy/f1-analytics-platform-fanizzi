"""Write one Monza telemetry replay from Kafka to TimescaleDB."""

import argparse
import os
from uuid import UUID

import psycopg
from pyspark.sql import DataFrame, SparkSession

from inspect_monza_2024_stream import read_monza_replay

INSERT_EVENTS = """
    INSERT INTO public.telemetry_events (
        event_time, published_at, replay_id, event_id, schema_version,
        source, event_type, session_key, meeting_key, driver_number,
        kafka_topic, kafka_partition, kafka_offset,
        speed, throttle, brake, rpm, n_gear, drs, x, y, z
    ) VALUES (
        %s::timestamptz, %s::timestamptz, %s::uuid, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (replay_id, event_time, event_id) DO NOTHING
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-id", type=UUID, required=True)
    parser.add_argument(
        "--follow", action="store_true",
        help="Keep writing new events until the query is stopped.",
    )
    args = parser.parse_args()
    password = os.environ.get("TIMESCALEDB_PASSWORD")
    if not password:
        parser.error("Set TIMESCALEDB_PASSWORD in the Spark container.")

    # Keep the writer's offsets separate from the inspection checkpoints.
    replay_id = str(args.replay_id)
    checkpoint_name = "monza_timescale_follow_v1" if args.follow else "monza_timescale_v1"
    checkpoint = f"/opt/spark/work-dir/checkpoints/{checkpoint_name}/{replay_id}"
    print(f"Writing replay: {replay_id}", flush=True)
    print(f"Checkpoint: {checkpoint}", flush=True)

    spark = (
        SparkSession.builder
        .appName("Monza2024TimescaleWriter")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")

    def write_batch(batch: DataFrame, batch_id: int) -> None:
        # The Kafka source caps the micro-batch size for this local job.
        # Pass the original timestamp strings with their UTC offsets to PostgreSQL.
        rows = batch.select(
            "event_time", "published_at", "replay_id", "event_id", "schema_version",
            "source", "event_type", "data.session_key", "data.meeting_key",
            "data.driver_number", "topic", "partition", "offset",
            "data.speed", "data.throttle", "data.brake", "data.rpm",
            "data.n_gear", "data.drs", "data.x", "data.y", "data.z",
        ).collect()
        if not rows:
            return

        # Commit the whole micro-batch before reporting success to Spark.
        # The primary key handles retries after a commit and repeated Kafka events.
        with psycopg.connect(
            host="timescaledb",
            port=5432,
            dbname="f1_telemetry",
            user="f1_telemetry_admin",
            password=password,
            connect_timeout=5,
        ) as conn, conn.cursor() as cursor:
            cursor.executemany(INSERT_EVENTS, rows)
            inserted = cursor.rowcount

        print(
            f"Batch {batch_id}: received={len(rows)} inserted={inserted} "
            f"duplicates={len(rows) - inserted}",
            flush=True,
        )

    try:
        events = read_monza_replay(spark, replay_id)
        # Drain the available backlog by default. Follow mode waits for new events.
        trigger = {"processingTime": "5 seconds"} if args.follow else {"availableNow": True}
        query = (
            events.writeStream
            .foreachBatch(write_batch)
            .outputMode("append")
            .option("checkpointLocation", checkpoint)
            .trigger(**trigger)
            .start()
        )
        query.awaitTermination()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
