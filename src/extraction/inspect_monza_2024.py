import fastf1


def main() -> None:
    """Load and inspect lap records from the 2024 Italian Grand Prix race."""

    # FastF1 stores downloaded responses in this directory.
    # On later runs, it can reuse them instead of requesting them again.
    # This relative path assumes that we run the script from the project root.
    fastf1.Cache.enable_cache("data/cache")

    # Select the event and session:
    # 2024 is the season, "Italian Grand Prix" is the Monza event,
    # and "R" means Race. This step only identifies the session.
    session = fastf1.get_session(2024, "Italian Grand Prix", "R")

    # Fetch the lap timing data for the selected race.
    # We leave out telemetry, weather, and messages for this first inspection.
    session.load(laps=True, telemetry=False, weather=False, messages=False)

    # session.laps is a table: each row represents one driver's lap record.
    laps = session.laps

    # Stop with a clear error if the source returned no lap records.
    if laps.empty:
        raise RuntimeError("No lap data was returned for this session.")

    # Check which session was loaded, how many rows it has,
    # and which fields are available for later analysis.
    print(f"Session: {session.event['EventName']} - {session.name}")
    print(f"Number of lap records: {len(laps)}")
    print(f"Columns: {laps.columns.tolist()}")

    # Group rows by driver and count the records in each group.
    # Adding these counts together gives the total number of lap records.
    print("Lap records by driver:")
    print(laps.groupby("Driver").size().rename("Lap records").to_string())

    # Show a small sample without printing the entire table.
    # The first ten rows may all belong to one driver because of row order.
    print("First 10 records:")
    print(laps[["Driver", "LapNumber", "LapTime", "Compound"]].head(10).to_string(index=False))


# Run main() when this file is executed directly from the terminal.
if __name__ == "__main__":
    main()
