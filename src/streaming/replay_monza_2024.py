"""Replay the saved Monza sample through Kafka at a controlled speed."""

import argparse
import json
import math
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from kafka import KafkaProducer
from kafka.serializer import DefaultSerializer, Serializer

from src.transformation.prepare_monza_2024_replay import RAW_FOLDER, prepare_events

TOPIC = "f1.telemetry.raw.v1"


class JsonEventSerializer(Serializer):
    """Encode events as strict UTF-8 JSON using the current Kafka interface."""

    def serialize(self, topic, headers, data):
        # Accept topic and headers as required by kafka-python 3.
        # Reject NaN and infinity rather than producing non-standard JSON.
        if data is None:
            return None
        return json.dumps(data, allow_nan=False).encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--speed", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--replay-id", type=UUID,
        help="Use a UUID chosen before starting the replay.",
    )
    args = parser.parse_args()
    if not math.isfinite(args.speed) or args.speed <= 0:
        parser.error("--speed must be finite and positive.")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be positive.")

    events = prepare_events(RAW_FOLDER)
    if args.limit is not None:
        events = events[:args.limit]

    replay_id = str(args.replay_id or uuid4())
    print(f"Replay ID: {replay_id}", flush=True)
    print(f"Topic: {TOPIC}; events: {len(events)}; speed: {args.speed}x", flush=True)

    producer = KafkaProducer(
        bootstrap_servers="127.0.0.1:9092",
        client_id="f1-monza-replay",
        enable_idempotence=True,
        acks="all",
        max_block_ms=10000,
        request_timeout_ms=10000,
        delivery_timeout_ms=20000,
        key_serializer=DefaultSerializer(),
        value_serializer=JsonEventSerializer(),
    )

    acknowledged = 0
    first_offset = None
    last_offset = None
    try:
        first_time = datetime.fromisoformat(events[0]["event_time"])
        clock_start = time.monotonic()

        for event in events:
            # Schedule against one monotonic clock to avoid accumulating
            # the time spent sending previous events into every delay.
            measured_at = datetime.fromisoformat(event["event_time"])
            elapsed_source = (measured_at - first_time).total_seconds()
            delay = clock_start + elapsed_source / args.speed - time.monotonic()
            if delay > 0:
                time.sleep(delay)

            # Preserve historical event time and record this publication
            # separately. Kafka's own timestamp uses the current send time.
            message = {
                **event,
                "replay_id": replay_id,
                "published_at": datetime.now(timezone.utc).isoformat(
                    timespec="microseconds"
                ),
            }
            key = (
                f"openf1:{event['data']['session_key']}:"
                f"{event['data']['driver_number']}"
            )
            result = producer.send(
                TOPIC, key=key, value=message
            ).get(timeout=25)

            acknowledged += 1
            offset = (result.partition, result.offset)
            if first_offset is None:
                first_offset = offset
            last_offset = offset

            if acknowledged % 50 == 0 or acknowledged == len(events):
                print(
                    f"Acknowledged {acknowledged}/{len(events)} events",
                    flush=True,
                )
    finally:
        # Idempotence handles producer retries within this producer session.
        # A new replay is a distinct run and is identified by replay_id.
        producer.close(timeout=5)

    print("First broker position (partition, offset):", first_offset)
    print("Last broker position (partition, offset):", last_offset)


if __name__ == "__main__":
    main()
