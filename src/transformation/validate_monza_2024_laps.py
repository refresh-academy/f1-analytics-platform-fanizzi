from pathlib import Path

import pandas as pd


def main() -> None:
    """Validate the raw lap records for the 2024 Monza race."""

    # Read the file produced by the extraction step.
    input_path = Path("data/raw/monza_2024_race_laps.parquet")
    laps = pd.read_parquet(input_path)

    # These columns are needed to identify and analyse a lap.
    required_columns = ["DriverNumber", "LapNumber", "LapTime", "Sector1Time"]
    missing_columns = set(required_columns) - set(laps.columns)

    if missing_columns:
        raise ValueError(f"Missing columns: {sorted(missing_columns)}")

    if laps.empty:
        raise ValueError("The lap dataset is empty.")

    # A lap must have a driver number and a lap number.
    lap_key = ["DriverNumber", "LapNumber"]
    if laps[lap_key].isna().any().any():
        raise ValueError("Some lap records have an incomplete key.")

    # Within this race, each driver/lap pair must occur once.
    if laps.duplicated(lap_key).any():
        raise ValueError("Duplicate driver/lap pairs found.")

    if laps["LapTime"].isna().any():
        raise ValueError("Some lap records have no lap time.")

    # The inspected source has missing sector 1 times on lap 1 only.
    # Keep those missing values, but flag missing values on later laps.
    unexpected_missing_sector1 = (
        laps["Sector1Time"].isna() & laps["LapNumber"].ne(1)
    )
    if unexpected_missing_sector1.any():
        raise ValueError("Sector 1 time is missing after lap 1.")

    print(f"Validation passed for {len(laps)} lap records.")


if __name__ == "__main__":
    main()
