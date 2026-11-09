"""Inspect one existing Monza replay using Spark Structured Streaming."""

import argparse
from collections import Counter
from uuid import UUID

from pyspark.sql import SparkSession, functions as F

TOPIC = "f1.telemetry.raw.v1"

# Explicit types prevent schema inference from depending on the first messages.
# Car and position events have different payload fields; fields belonging to
# the other event type are expected to be null in this combined Spark schema.
EVENT_SCHEMA = """
    schema_version INT,
    event_id STRING,
    source STRING,
    event_type STRING,
    event_time STRING,
    replay_id STRING,
    published_at STRING,
    data STRUCT<
        date: STRING,
        session_key: BIGINT,
        meeting_key: BIGINT,
        driver_number: INT,
        rpm: INT,
        n_gear: INT,
        drs: INT,
        throttle: INT,
        speed: INT,
        brake: INT,
        x: INT,
        y: INT,
        z: INT
    >
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-id", type=UUID, required=True)
    args = parser.parse_args()
    replay_id = str(args.replay_id)

    # Keep progress separate for each replay and inspection-query version.
    checkpoint = (
        f"/opt/spark/work-dir/checkpoints/monza_inspect_v1/{replay_id}"
    )
    print(f"Inspecting replay: {replay_id}", flush=True)
    print(f"Checkpoint: {checkpoint}", flush=True)

    spark = (
        SparkSession.builder
        .appName("Monza2024ReplayInspection")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    totals = Counter()

    try:
        # Containers reach the broker through its internal Compose address.
        # earliest applies only to a new query; a saved checkpoint takes
        # precedence when the same inspection is started again.
        raw = (
            spark.readStream.format("kafka")
            .option("kafka.bootstrap.servers", "kafka:19092")
            .option("subscribe", TOPIC)
            .option("startingOffsets", "earliest")
            .option("maxOffsetsPerTrigger", 1000)
            .option("failOnDataLoss", "true")
            .load()
        )

        # Kafka supplies bytes. Decode JSON explicitly and keep broker offsets
        # so displayed records can be traced back to their stored messages.
        events = (
            raw.select(
                "topic", "partition", "offset",
                F.col("key").cast("string").alias("kafka_key"),
                F.from_json(
                    F.col("value").cast("string"),
                    EVENT_SCHEMA,
                    {"mode": "FAILFAST"},
                ).alias("event"),
            )
            .select("topic", "partition", "offset", "kafka_key", "event.*")
            .filter(F.col("replay_id") == replay_id)
            .withColumn("event_time_utc", F.to_timestamp("event_time"))
            .withColumn("published_at_utc", F.to_timestamp("published_at"))
        )

        def inspect_batch(batch, batch_id):
            # Several displays reuse this batch, so cache it temporarily.
            cached = batch.persist()
            try:
                counts = {
                    row["event_type"]: row["count"]
                    for row in cached.groupBy("event_type").count().collect()
                }
                totals.update(counts)
                print(f"Batch {batch_id}: {counts}", flush=True)

                # Show each payload type separately: a position sample does
                # not contain speed, and a car sample does not contain X/Y.
                print("Car telemetry examples:", flush=True)
                (
                    cached.filter(F.col("event_type") == "car_data")
                    .select(
                        "offset", "event_time_utc",
                        "data.speed", "data.throttle", "data.brake",
                    )
                    .orderBy("offset")
                    .show(5, truncate=False)
                )
                print("Position examples:", flush=True)
                (
                    cached.filter(F.col("event_type") == "location")
                    .select("offset", "event_time_utc", "data.x", "data.y")
                    .orderBy("offset")
                    .show(5, truncate=False)
                )
            finally:
                cached.unpersist()

        # Process the backlog available at startup, checkpoint progress,
        # and finish. A later step will introduce an ongoing live query.
        query = (
            events.writeStream
            .foreachBatch(inspect_batch)
            .outputMode("append")
            .option("checkpointLocation", checkpoint)
            .trigger(availableNow=True)
            .start()
        )
        query.awaitTermination()

        print("Events inspected in this invocation:", sum(totals.values()))
        print("Counts:", dict(totals))
        if not totals:
            print("No matching events were emitted; an existing checkpoint may be up to date.")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
