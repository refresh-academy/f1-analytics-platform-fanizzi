from pathlib import Path

import fastf1


def main() -> None:
    """Save the 2024 Italian Grand Prix race laps as raw Parquet data."""

    # Reuse responses downloaded during the earlier inspection.
    fastf1.Cache.enable_cache("data/cache")

    # Select the race and load its lap records.
    session = fastf1.get_session(2024, "Italian Grand Prix", "R")
    session.load(laps=True, telemetry=False, weather=False, messages=False)
    laps = session.laps

    # Avoid creating a file that appears valid but contains no records.
    if laps.empty:
        raise RuntimeError("No lap data was returned for this session.")

    # Keep all source columns. The DataFrame index is not a source column.
    output_path = Path("data/raw/monza_2024_race_laps.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    laps.to_parquet(output_path, engine="pyarrow", index=False)

    print(f"Saved {len(laps)} lap records to {output_path}")


if __name__ == "__main__":
    main()
