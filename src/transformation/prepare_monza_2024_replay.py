"""Prepare the saved OpenF1 sample as chronologically ordered replay events."""

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

RAW_FOLDER = Path("data/raw/openf1_monza_2024_leclerc_lap_10")


def prepare_events(folder: Path) -> list[dict]:
    """Build events from the local snapshot without publishing them."""
    manifest = json.loads(
        (folder / "manifest.json").read_text(encoding="utf-8")
    )
    if manifest["source"] != "OpenF1":
        raise ValueError("Expected an OpenF1 source snapshot.")

    events = []
    for event_type in ("car_data", "location"):
        frame = pd.read_parquet(folder / f"{event_type}.parquet")
        if frame.empty or len(frame) != manifest["row_counts"][event_type]:
            raise ValueError(f"{event_type}: row count differs from manifest.")

        # JSON conversion produces ordinary Python values for serialization.
        # Each source record remains inside the event's data field.
        records = json.loads(frame.to_json(orient="records"))
        for record in records:
            for field in ("session_key", "driver_number"):
                if record[field] != manifest["lap_record"][field]:
                    raise ValueError(f"{event_type}: unexpected {field}.")

            measured_at = datetime.fromisoformat(record["date"])
            if measured_at.utcoffset() is None:
                raise ValueError("Source timestamp must include a timezone.")
            event_time = measured_at.astimezone(timezone.utc).isoformat(
                timespec="microseconds"
            )

            # Identify the source sample independently of when it is replayed.
            # Including the stream type distinguishes car and position samples.
            identity = [
                "openf1", event_type, record["session_key"],
                record["driver_number"], event_time,
            ]
            event_id = hashlib.sha256(
                json.dumps(identity, separators=(",", ":")).encode("utf-8")
            ).hexdigest()

            events.append({
                "schema_version": 1,
                "event_id": event_id,
                "source": "openf1",
                "event_type": event_type,
                "event_time": event_time,
                "data": record,
            })

    if len({event["event_id"] for event in events}) != len(events):
        raise ValueError("Duplicate source sample identities detected.")

    # UTC timestamps use the same fixed format, so text ordering is chronological.
    # Secondary fields make the ordering deterministic when timestamps are equal.
    events.sort(key=lambda event: (
        event["event_time"], event["event_type"], event["event_id"]
    ))
    return events


def main() -> None:
    events = prepare_events(RAW_FOLDER)
    counts = Counter(event["event_type"] for event in events)
    print(f"Prepared events: {len(events)}")
    for event_type in ("car_data", "location"):
        print(f"{event_type}: {counts[event_type]}")
    print("First event:", events[0]["event_time"], events[0]["event_type"])
    print("Last event:", events[-1]["event_time"], events[-1]["event_type"])
    print("Event IDs are unique; events are ordered chronologically.")


if __name__ == "__main__":
    main()
