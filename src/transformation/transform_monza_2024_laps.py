from pathlib import Path

import pandas as pd


def main() -> None:
    """Create an analysis-ready lap dataset from the raw Monza race data."""

    # Read the source without changing the raw Parquet file.
    input_path = Path("data/raw/monza_2024_race_laps.parquet")
    laps = pd.read_parquet(input_path)

    if laps.empty:
        raise ValueError("The raw lap dataset is empty.")

    # The source stores lap numbers as floats, such as 1.0.
    # Check again before converting them to integers.
    if laps["LapNumber"].isna().any() or not laps["LapNumber"].mod(1).eq(0).all():
        raise ValueError("Lap numbers must be present and whole.")

    # Preserve FastF1's timing-quality flag without using it to discard laps.
    if laps["IsAccurate"].isna().any():
        raise ValueError("IsAccurate must be present for every lap.")

    # Add session identifiers so a lap remains identifiable when
    # we later process more races. Convert durations to seconds.
    processed = pd.DataFrame(
        {
            "season": 2024,
            "event_name": "Italian Grand Prix",
            "session_name": "Race",
            "driver_number": laps["DriverNumber"].astype("string"),
            "lap_number": laps["LapNumber"].astype("int64"),
            "lap_time_seconds": laps["LapTime"].dt.total_seconds(),
            "sector1_seconds": laps["Sector1Time"].dt.total_seconds(),
            "sector2_seconds": laps["Sector2Time"].dt.total_seconds(),
            "sector3_seconds": laps["Sector3Time"].dt.total_seconds(),
            "compound": laps["Compound"].astype("string"),
            "is_accurate": laps["IsAccurate"].astype("bool"),
        }
    )

    # Missing sector times remain missing; do not replace them with zero.
    output_path = Path("data/processed/monza_2024_race_laps.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    processed.to_parquet(output_path, engine="pyarrow", index=False)

    print(f"Saved {len(processed)} processed lap records to {output_path}")
    print(f"Columns: {processed.columns.tolist()}")


if __name__ == "__main__":
    main()
