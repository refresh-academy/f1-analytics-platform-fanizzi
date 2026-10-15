"""Extract the complete 2024 Monza race results to raw Parquet."""

from pathlib import Path

import fastf1


def main() -> None:
    # FastF1 stores downloaded session data here for later runs.
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(cache_dir))

    session = fastf1.get_session(2024, "Monza", "R")
    session.load(telemetry=False, weather=False, messages=False)
    results = session.results

    # Stop before writing a misleading empty source file.
    if results.empty:
        raise RuntimeError("No race results were returned for this session.")

    # Preserve all source columns, including driver details and race results.
    output_path = Path("data/raw/monza_2024_race_results.parquet")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_parquet(output_path, engine="pyarrow", index=False)

    print(f"Saved {len(results)} race result records to {output_path}")
    print(f"Source columns: {results.columns.tolist()}")


if __name__ == "__main__":
    main()
