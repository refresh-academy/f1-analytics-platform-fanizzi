from pathlib import Path

import pandas as pd


def main() -> None:
    """Inspect data types and missing values in the raw lap records."""

    # Read the local Parquet file produced by the extraction step.
    input_path = Path("data/raw/monza_2024_race_laps.parquet")
    laps = pd.read_parquet(input_path)

    # Start with fields that identify a lap or describe its timing and tyre.
    columns = [
        "Driver",
        "LapNumber",
        "LapTime",
        "Sector1Time",
        "Sector2Time",
        "Sector3Time",
        "Compound",
    ]

    print(f"Number of records: {len(laps)}")

    # A data type tells us how pandas represents each field in memory.
    print("\nData types:")
    print(laps[columns].dtypes.to_string())

    # isna() marks missing values; sum() counts them in each column.
    print("\nMissing values:")
    print(laps[columns].isna().sum().to_string())


if __name__ == "__main__":
    main()
