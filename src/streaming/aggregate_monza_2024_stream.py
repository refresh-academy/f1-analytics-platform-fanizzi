"""Calculate five-second speed windows for one Monza telemetry replay."""

import argparse
import os
from uuid import UUID

import psycopg
from pyspark.sql import DataFrame, SparkSession, functions as F
from pyspark.sql.streaming import StreamingQuery

from inspect_monza_2024_stream import read_monza_replay

WINDOW_DURATION = "5 seconds"
WATERMARK_DELAY = "10 seconds"
TIMESTAMP_FORMAT = "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX"

UPSERT_WINDOWS = """
    INSERT INTO public.telemetry_speed_5s AS stored (
        window_start, window_end, replay_id, session_key, driver_number,
        sample_count, avg_speed_kmh, min_speed_kmh, max_speed_kmh
    ) VALUES (
        %s::timestamptz, %s::timestamptz, %s::uuid, %s, %s,
        %s, %s, %s, %s
    )
    ON CONFLICT (replay_id, session_key, driver_number, window_start)
    DO UPDATE SET
        window_end = EXCLUDED.window_end,
        sample_count = EXCLUDED.sample_count,
        avg_speed_kmh = EXCLUDED.avg_speed_kmh,
        min_speed_kmh = EXCLUDED.min_speed_kmh,
        max_speed_kmh = EXCLUDED.max_speed_kmh,
        updated_at = CURRENT_TIMESTAMP
    WHERE EXCLUDED.sample_count >= stored.sample_count
      AND (stored.sample_count, stored.avg_speed_kmh,
           stored.min_speed_kmh, stored.max_speed_kmh)
          IS DISTINCT FROM
          (EXCLUDED.sample_count, EXCLUDED.avg_speed_kmh,
           EXCLUDED.min_speed_kmh, EXCLUDED.max_speed_kmh)
"""


def speed_windows(events: DataFrame) -> DataFrame:
    """Keep unique source samples and update their event-time window statistics."""
    # Position records have no speed. A missing speed does not mean zero speed.
    cars = events.filter(
        (F.col("event_type") == "car_data") & F.col("data.speed").isNotNull()
    ).select(
        F.coalesce("event_time_utc", F.raise_error("Missing event time.")).alias(
            "event_time_utc"
        ),
        "replay_id",
        F.col("data.session_key").alias("session_key"),
        F.col("data.driver_number").alias("driver_number"),
        F.coalesce("event_id", F.raise_error("Missing event ID.")).alias("event_id"),
        F.col("data.speed").alias("speed"),
    )

    # The watermark follows the maximum historical event time seen by this query.
    # It is independent of today's clock and bounds how long old windows stay active.
    grouped = (
        cars.withWatermark("event_time_utc", WATERMARK_DELAY)
        .groupBy(
            "replay_id", "session_key", "driver_number",
            F.window("event_time_utc", WINDOW_DURATION).alias("window"),
        )
        # Keep distinct events, not distinct speed values: two samples can have
        # the same speed. This also deduplicates repeated messages across batches.
        # Set size grows with the unique samples in each active window; this
        # approach is intended for the current small telemetry replay.
        .agg(F.collect_set(F.struct("event_id", "speed")).alias("samples"))
    )

    speeds = F.transform("samples", lambda sample: sample["speed"])
    event_ids = F.transform("samples", lambda sample: sample["event_id"])
    count = F.size("samples")
    total = F.aggregate(speeds, F.lit(0).cast("long"), lambda acc, speed: acc + speed)

    # An immutable event ID must not represent two different speed values.
    checked_count = F.when(
        F.size(F.array_distinct(event_ids)) == count, count
    ).otherwise(F.raise_error("Conflicting speeds for the same event ID."))

    return grouped.select(
        F.col("window.start").alias("window_start"),
        F.col("window.end").alias("window_end"),
        "replay_id", "session_key", "driver_number",
        checked_count.cast("long").alias("sample_count"),
        (total.cast("double") / count).alias("avg_speed_kmh"),
        F.array_min(speeds).alias("min_speed_kmh"),
        F.array_max(speeds).alias("max_speed_kmh"),
    )


def start_speed_query(
    spark: SparkSession, replay_id: str, password: str, *, follow: bool = False
) -> StreamingQuery:
    """Start the metrics query with its own Kafka offsets and aggregation state."""
    checkpoint_name = "monza_speed_5s_follow_v1" if follow else "monza_speed_5s_v1"
    checkpoint = f"/opt/spark/work-dir/checkpoints/{checkpoint_name}/{replay_id}"
    print(f"Aggregating replay: {replay_id}", flush=True)
    print(f"Checkpoint: {checkpoint}", flush=True)

    def write_windows(batch: DataFrame, batch_id: int) -> None:
        # Collect all emitted windows so the stateful batch is fully consumed.
        # Explicit UTC offsets avoid relying on Python or PostgreSQL local time.
        rows = batch.select(
            F.date_format("window_start", TIMESTAMP_FORMAT),
            F.date_format("window_end", TIMESTAMP_FORMAT),
            "replay_id", "session_key", "driver_number", "sample_count",
            "avg_speed_kmh", "min_speed_kmh", "max_speed_kmh",
        ).collect()
        if not rows:
            return

        # Replace cumulative values rather than adding them again on a retry.
        # Do not overwrite a more complete stored window with a partial rebuild.
        # Identical results leave updated_at unchanged. Commit the whole batch.
        with psycopg.connect(
            host="timescaledb", port=5432, dbname="f1_telemetry",
            user="f1_telemetry_admin", password=password, connect_timeout=5,
        ) as conn, conn.cursor() as cursor:
            cursor.executemany(UPSERT_WINDOWS, rows)
            changed = cursor.rowcount

        print(
            f"Metrics batch {batch_id}: windows_received={len(rows)} "
            f"windows_changed={changed}",
            flush=True,
        )

    metrics = speed_windows(read_monza_replay(spark, replay_id))
    trigger = {"processingTime": "5 seconds"} if follow else {"availableNow": True}
    return (
        metrics.writeStream
        .foreachBatch(write_windows)
        # Update mode emits current values, including the last windows of a
        # finite replay. These rows are latest-known aggregates, not a claim
        # that the watermark has finalized every stored window.
        .outputMode("update")
        .option("checkpointLocation", checkpoint)
        .trigger(**trigger)
        .start()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-id", type=UUID, required=True)
    parser.add_argument(
        "--follow", action="store_true",
        help="Keep updating windows until the query is stopped.",
    )
    args = parser.parse_args()
    password = os.environ.get("TIMESCALEDB_PASSWORD")
    if not password:
        parser.error("Set TIMESCALEDB_PASSWORD in the Spark container.")

    spark = (
        SparkSession.builder
        .appName("Monza2024SpeedWindows")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.adaptive.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    try:
        query = start_speed_query(spark, str(args.replay_id), password, follow=args.follow)
        query.awaitTermination()
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
