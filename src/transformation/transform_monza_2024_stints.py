"""Prepare Monza race stints for warehouse loading."""

from pathlib import Path

import pandas as pd


def main():
    # Read the original lap data, selecting only the fields needed here.
    # Each source row represents one recorded lap, not one complete stint.
    source_path = Path("data/raw/monza_2024_race_laps.parquet")
    laps = pd.read_parquet(
        source_path,
        columns=["DriverNumber", "LapNumber", "Stint", "Compound"],
    )

    # An empty input would produce an empty output without explaining why.
    if laps.empty:
        raise ValueError("No source laps were found.")

    # Every output stint needs a driver, lap number, stint number, and compound.
    required = ["DriverNumber", "LapNumber", "Stint", "Compound"]
    if laps[required].isna().any().any():
        raise ValueError("A required stint field is missing.")

    # FastF1 stores LapNumber and Stint as floats in this source.
    # For example, 2.0 can safely become the integer 2, but 2.5 cannot.
    for column in ["LapNumber", "Stint"]:
        if not laps[column].mod(1).eq(0).all():
            raise ValueError(f"{column} contains a non-whole number.")

    # Group laps by driver and source stint number.
    # The aggregation turns many lap rows into one summary row per stint:
    # size counts recorded laps; min and max locate its lap-number boundaries.
    stints = (
        laps.groupby(["DriverNumber", "Stint"], as_index=False)
        .agg(
            compound=("Compound", "first"),
            distinct_compounds=("Compound", "nunique"),
            recorded_laps=("LapNumber", "size"),
            first_lap=("LapNumber", "min"),
            last_lap=("LapNumber", "max"),
        )
        # Sorting places each driver's stints in their numbered order.
        .sort_values(["DriverNumber", "Stint"])
        .reset_index(drop=True)
    )

    # Taking the first compound is safe only if every lap in that stint
    # reports the same compound. Check this before saving the output.
    if stints["distinct_compounds"].ne(1).any():
        raise ValueError("A stint contains multiple compounds.")

    # For a continuous range, its size equals last_lap - first_lap + 1.
    # For example, laps 5 through 8 contain four recorded laps.
    if stints["recorded_laps"].ne(
        stints["last_lap"] - stints["first_lap"] + 1
    ).any():
        raise ValueError("A stint contains a gap in its recorded laps.")

    # shift() retrieves the end of the previous stint for the same driver.
    # The next stint must begin on the following lap.
    previous_last_lap = stints.groupby("DriverNumber")["last_lap"].shift()
    if (
        previous_last_lap.notna()
        & stints["first_lap"].ne(previous_last_lap + 1)
    ).any():
        raise ValueError("There is a gap between consecutive stints.")

    # distinct_compounds was needed for validation, not for the output.
    # Rename source fields to match the warehouse naming convention.
    stints = stints.drop(columns="distinct_compounds").rename(
        columns={
            "DriverNumber": "driver_number",
            "Stint": "stint_number",
        }
    )

    # Convert whole-number floats into integers after checking their values.
    stints[["stint_number", "first_lap", "last_lap"]] = stints[
        ["stint_number", "first_lap", "last_lap"]
    ].astype(int)

    # A stint number can repeat in another race or for another driver.
    # These fields identify which session the stint belongs to.
    stints.insert(0, "session_name", "Race")
    stints.insert(0, "event_name", "Italian Grand Prix")
    stints.insert(0, "season", 2024)

    # Store the processed result separately from the unchanged raw source.
    # The DataFrame index is not a source or warehouse field.
    output_path = Path("data/processed/monza_2024_race_stints.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    stints.to_parquet(output_path, engine="pyarrow", index=False)

    print(f"Saved {len(stints)} stint records to {output_path}")
    print(f"Recorded laps across stints: {stints['recorded_laps'].sum()}")
    print(f"Columns: {stints.columns.tolist()}")


if __name__ == "__main__":
    main()
