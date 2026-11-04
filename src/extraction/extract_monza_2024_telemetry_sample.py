"""Extract an OpenF1 telemetry sample for Leclerc, Monza 2024, lap 10."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import requests

API_URL = "https://api.openf1.org/v1"
SESSION_KEY = 9590
DRIVER_NUMBER = 16
LAP_NUMBER = 10
OUTPUT_DIR = Path("data/raw/openf1_monza_2024_leclerc_lap_10")


def fetch_records(endpoint: str, params: dict) -> list:
    """Fetch one bounded request and reject failed or empty responses."""
    response = requests.get(
        f"{API_URL}/{endpoint}", params=params, timeout=30
    )
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list) or not records:
        raise RuntimeError(f"No records returned by OpenF1 endpoint: {endpoint}")
    return records


def main() -> None:
    # Keep an existing raw snapshot intact instead of silently replacing it.
    if OUTPUT_DIR.exists():
        raise FileExistsError(f"Raw snapshot already exists: {OUTPUT_DIR}")

    identity = {"session_key": SESSION_KEY, "driver_number": DRIVER_NUMBER}
    laps = fetch_records("laps", {**identity, "lap_number": LAP_NUMBER})
    if len(laps) != 1:
        raise RuntimeError("Expected exactly one source lap record.")
    lap = laps[0]

    # OpenF1's lap start is approximate. Preserve the source lap record
    # so this sampling window remains traceable rather than claiming
    # independently verified start/finish crossing timestamps.
    start = datetime.fromisoformat(lap["date_start"])
    duration = float(lap["lap_duration"])
    if start.utcoffset() is None or not 0 < duration < float("inf"):
        raise ValueError("Invalid source lap timestamp or duration.")
    end = start + timedelta(seconds=duration)
    query = {**identity, "date>": start.isoformat(), "date<": end.isoformat()}

    required_channels = {
        "car_data": ["speed", "rpm", "n_gear", "throttle", "brake", "drs"],
        "location": ["x", "y", "z"],
    }
    frames = {}
    for endpoint, channels in required_channels.items():
        frame = pd.DataFrame(fetch_records(endpoint, query))
        required = {"date", "session_key", "driver_number", *channels}
        missing = required.difference(frame.columns)
        if missing:
            raise ValueError(f"{endpoint}: missing columns {sorted(missing)}")
        for column, expected in identity.items():
            if not frame[column].eq(expected).all():
                raise ValueError(f"{endpoint}: unexpected {column}")

        # Parse timestamps for validation while keeping the source columns
        # unchanged in the raw Parquet. Do not sort, merge, or interpolate.
        dates = pd.to_datetime(
            frame["date"], format="ISO8601", utc=True, errors="raise"
        )
        if dates.isna().any() or not (
            dates.gt(pd.Timestamp(start)) & dates.lt(pd.Timestamp(end))
        ).all():
            raise ValueError(f"{endpoint}: invalid or out-of-window timestamp")
        frames[endpoint] = frame

    manifest = {
        "source": "OpenF1",
        "api_base_url": API_URL,
        "extracted_at_utc": datetime.now(timezone.utc).isoformat(),
        "lap_record": lap,
        "sample_query": query,
        "row_counts": {name: len(frame) for name, frame in frames.items()},
    }

    # Publish the snapshot only after both downloads and all file writes
    # succeed. Temporary files stay inside the ignored raw-data directory.
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=OUTPUT_DIR.parent, prefix="openf1_tmp_") as temp:
        temporary = Path(temp)
        for name, frame in frames.items():
            frame.to_parquet(
                temporary / f"{name}.parquet", engine="pyarrow", index=False
            )
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        temporary.rename(OUTPUT_DIR)

    print(f"Saved raw snapshot to {OUTPUT_DIR}")
    for name, frame in frames.items():
        print(f"{name}: {len(frame)} samples")


if __name__ == "__main__":
    main()
