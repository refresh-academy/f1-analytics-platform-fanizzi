"""Load processed Monza race laps into the PostgreSQL staging table."""

import os
from pathlib import Path

import pandas as pd
import psycopg


def main() -> None:
    input_path = Path("data/processed/monza_2024_race_laps.parquet")
    laps = pd.read_parquet(input_path)

    # The column order must match the placeholders in the INSERT statement.
    columns = [
        "season",
        "event_name",
        "session_name",
        "driver_number",
        "lap_number",
        "lap_time_seconds",
        "sector1_seconds",
        "sector2_seconds",
        "sector3_seconds",
        "compound",
        "is_accurate",
    ]
    if laps.empty or laps.columns.tolist() != columns:
        raise ValueError("The processed lap file is empty or has unexpected columns.")

    # Require the source quality flag before writing to PostgreSQL.
    if laps["is_accurate"].isna().any():
        raise ValueError("is_accurate must be present for every lap.")

    # Convert missing pandas values to Python None, which becomes SQL NULL.
    records = (
        laps.astype(object)
        .where(laps.notna(), None)
        .itertuples(index=False, name=None)
    )

    # The primary key identifies a driver's lap within one session.
    # Update an existing lap only when at least one measurement has changed.
    insert_sql = """
        INSERT INTO staging.laps (
            season, event_name, session_name, driver_number, lap_number,
            lap_time_seconds, sector1_seconds, sector2_seconds,
            sector3_seconds, compound, is_accurate
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT laps_pkey DO UPDATE SET
            lap_time_seconds = EXCLUDED.lap_time_seconds,
            sector1_seconds = EXCLUDED.sector1_seconds,
            sector2_seconds = EXCLUDED.sector2_seconds,
            sector3_seconds = EXCLUDED.sector3_seconds,
            compound = EXCLUDED.compound,
            is_accurate = EXCLUDED.is_accurate
        WHERE (
            laps.lap_time_seconds,
            laps.sector1_seconds,
            laps.sector2_seconds,
            laps.sector3_seconds,
            laps.compound,
            laps.is_accurate
        ) IS DISTINCT FROM (
            EXCLUDED.lap_time_seconds,
            EXCLUDED.sector1_seconds,
            EXCLUDED.sector2_seconds,
            EXCLUDED.sector3_seconds,
            EXCLUDED.compound,
            EXCLUDED.is_accurate
        )
    """

    # A successful connection block commits; an error rolls the changes back.
    with psycopg.connect(
        host="127.0.0.1",
        port=5433,
        dbname="f1_analytics",
        user="f1_admin",
        password=os.environ["POSTGRES_PASSWORD"],
    ) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(insert_sql, records)

            # Read this before the SELECT: the next command changes rowcount.
            affected_rows = cursor.rowcount

            cursor.execute("SELECT COUNT(*) FROM staging.laps")
            total_rows = cursor.fetchone()[0]

    print(f"Processed lap records: {len(laps)}")
    print(f"Rows inserted or updated: {affected_rows}")
    print(f"Rows currently in staging.laps: {total_rows}")


if __name__ == "__main__":
    main()
