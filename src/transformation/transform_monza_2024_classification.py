"""Prepare Monza 2024 race classification from the preserved raw results."""

from pathlib import Path

import pandas as pd


def main() -> None:
    source = Path("data/raw/monza_2024_race_results.parquet")
    columns = [
        "DriverNumber", "Position", "ClassifiedPosition", "Laps", "Status"
    ]
    # Read only the fields needed for classification. Keep the raw
    # Parquet snapshot unchanged so the source remains available.
    results = pd.read_parquet(source, columns=columns)

    if results.empty:
        raise ValueError("The race results contain no classification records.")

    # Missing driver identifiers or classification text would make
    # the resulting warehouse rows ambiguous.
    for name in ("DriverNumber", "ClassifiedPosition", "Status"):
        if results[name].isna().any() or results[name].astype(str).str.strip().eq("").any():
            raise ValueError(f"Missing values in {name}.")

    # Convert the source numbers explicitly before storing them as
    # integers; reject missing, fractional, or invalid values.
    position = pd.to_numeric(results["Position"], errors="raise")
    laps = pd.to_numeric(results["Laps"], errors="raise")
    if position.isna().any() or position.lt(1).any() or position.mod(1).ne(0).any():
        raise ValueError("Result positions must be positive whole numbers.")
    if laps.isna().any() or laps.lt(0).any() or laps.mod(1).ne(0).any():
        raise ValueError("Completed lap counts must be nonnegative whole numbers.")

    # Each driver and result-order position must occur only once in
    # this race. Exactly one row must identify the first-place result.
    driver_number = results["DriverNumber"].astype(str).str.strip()
    if driver_number.duplicated().any() or position.duplicated().any():
        raise ValueError("Duplicate driver numbers or result positions.")
    if position.eq(1).sum() != 1:
        raise ValueError("Expected exactly one first-place result.")

    # Position orders the source results. ClassifiedPosition remains
    # text so a retirement marker such as "R" is not lost. Attach the
    # race identifiers needed to connect these rows to a session.
    classification = pd.DataFrame({
        "season": 2024,
        "event_name": "Italian Grand Prix",
        "session_name": "Race",
        "driver_number": driver_number,
        "result_position": position.astype("int64"),
        "classified_position": results["ClassifiedPosition"].astype(str).str.strip(),
        "laps_completed": laps.astype("int64"),
        "status": results["Status"].astype(str).str.strip(),
    })

    output = Path("data/processed/monza_2024_race_classification.parquet")
    output.parent.mkdir(parents=True, exist_ok=True)
    classification.to_parquet(output, engine="pyarrow", index=False)
    print(f"Saved {len(classification)} race results to {output}")
    print(classification.sort_values("result_position").head(5).to_string(index=False))


if __name__ == "__main__":
    main()
