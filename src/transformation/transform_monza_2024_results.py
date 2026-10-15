"""Prepare Monza race driver details for warehouse loading."""

from pathlib import Path

import pandas as pd


def main():
    # Read only the source fields needed for the driver model.
    source_path = Path("data/raw/monza_2024_race_results.parquet")
    source_columns = [
        "DriverNumber",
        "DriverId",
        "Abbreviation",
        "FullName",
        "TeamName",
    ]
    results = pd.read_parquet(source_path, columns=source_columns)

    if results.empty:
        raise ValueError("The race results contain no drivers.")

    # Missing identifiers or names would prevent reliable joins later.
    for column in source_columns:
        if results[column].isna().any() or results[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Missing values in {column}.")

    if results["DriverNumber"].duplicated().any():
        raise ValueError("Duplicate driver numbers in the race results.")
    if results["DriverId"].duplicated().any():
        raise ValueError("Duplicate driver IDs in the race results.")

    drivers = results.rename(
        columns={
            "DriverNumber": "driver_number",
            "DriverId": "driver_id",
            "Abbreviation": "abbreviation",
            "FullName": "full_name",
            "TeamName": "team_name",
        }
    ).copy()

    # The team and race number describe this session; they can change later.
    drivers.insert(0, "session_name", "Race")
    drivers.insert(0, "event_name", "Italian Grand Prix")
    drivers.insert(0, "season", 2024)

    output_path = Path("data/processed/monza_2024_race_drivers.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    drivers.to_parquet(output_path, engine="pyarrow", index=False)

    print(f"Saved {len(drivers)} driver records to {output_path}")
    print(f"Columns: {drivers.columns.tolist()}")
    print(drivers[["driver_number", "full_name", "team_name"]].head().to_string(index=False))


if __name__ == "__main__":
    main()
