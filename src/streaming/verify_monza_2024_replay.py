"""Verify one complete Monza sample replay against the local source events."""

import argparse
import json
from collections import Counter
from datetime import datetime

from kafka import KafkaConsumer, TopicPartition

from src.streaming.replay_monza_2024 import TOPIC
from src.transformation.prepare_monza_2024_replay import RAW_FOLDER, prepare_events


def main() -> None:
    # A topic can contain several replay runs, including our earlier smoke tests.
    # The replay ID and offset interval identify the run we want to inspect.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay-id", required=True)
    parser.add_argument("--start-offset", type=int, required=True)
    parser.add_argument("--end-offset", type=int, required=True)
    args = parser.parse_args()

    # Offsets are positions within a Kafka partition, not source event IDs.
    # Our selected interval includes both its first and last offset.
    if args.start_offset < 0 or args.end_offset < args.start_offset:
        parser.error("Offsets must define a non-negative, ordered interval.")

    # Reconstruct the expected events from the saved Parquet snapshot.
    # This uses local data and makes no new requests to OpenF1.
    expected = prepare_events(RAW_FOLDER)
    if len(expected) != args.end_offset - args.start_offset + 1:
        raise ValueError("Offset interval must cover the complete source sample.")

    received = []
    consumer = KafkaConsumer(
        bootstrap_servers="127.0.0.1:9092",
        # This diagnostic reader does not belong to a consumer group and
        # must not advance a checkpoint that another application could use.
        group_id=None,
        enable_auto_commit=False,
        # Fail if the requested offsets are unavailable rather than silently
        # jumping to the earliest or latest available messages.
        auto_offset_reset="none",
        # Stop waiting if no records arrive; the count check below will
        # report an incomplete read instead of declaring success.
        consumer_timeout_ms=10000,
    )

    # The local sample topic has one partition, numbered zero.
    partition = TopicPartition(TOPIC, 0)

    try:
        # Explicit assignment and seek make this read reproducible:
        # start at the requested broker position, regardless of earlier reads.
        consumer.assign([partition])
        consumer.seek(partition, args.start_offset)

        for record in consumer:
            if record.offset > args.end_offset:
                break

            # This check expects a contiguous interval for our isolated run.
            # Missing offsets must be investigated rather than skipped.
            index = len(received)
            if record.offset != args.start_offset + index:
                raise ValueError("Unexpected gap in broker offsets.")

            # Kafka returns bytes by default. Parse the JSON message before
            # checking its fields against the locally prepared event.
            event = json.loads(record.value)
            if event.get("replay_id") != args.replay_id:
                raise ValueError("Unexpected replay ID in the selected interval.")

            # Compare every prepared field, including event_time, event_id,
            # schema_version, and the complete original source payload.
            # replay_id and published_at are added during publication and
            # are checked separately because they vary between executions.
            original = expected[index]
            if {field: event.get(field) for field in original} != original:
                raise ValueError(f"Event differs at offset {record.offset}.")

            # The key identifies the source session and driver for routing.
            # It is deliberately different from the ID of an individual sample.
            data = original["data"]
            key = f"openf1:{data['session_key']}:{data['driver_number']}"
            if record.key != key.encode("utf-8"):
                raise ValueError("Unexpected message key.")

            received.append(event)
            if record.offset == args.end_offset:
                break
    finally:
        # Release connections even if a validation check raises an exception.
        consumer.close()

    # Reaching a timeout or the end of the available records is insufficient:
    # every expected source event must have been received and compared.
    if len(received) != len(expected):
        raise RuntimeError(f"Read {len(received)} of {len(expected)} events.")

    # Compare the historical sample span with the publication span.
    # These are first-to-last durations, not per-event latency measurements.
    spans = {}
    for field in ("event_time", "published_at"):
        spans[field] = (
            datetime.fromisoformat(received[-1][field])
            - datetime.fromisoformat(received[0][field])
        ).total_seconds()

    # Print a compact summary instead of dumping all 647 messages.
    print("Verified events:", len(received))
    print("Event counts:", dict(Counter(e["event_type"] for e in received)))
    print("Replay ID:", args.replay_id)
    print("All keys, source contents, event IDs, and ordering match.")
    for field, seconds in spans.items():
        print(f"{field} span: {seconds:.3f} seconds")


if __name__ == "__main__":
    main()
