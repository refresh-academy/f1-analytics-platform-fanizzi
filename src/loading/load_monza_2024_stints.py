"""Load processed Monza stints into PostgreSQL staging."""

import os
from pathlib import Path

import pandas as pd
import psycopg


def main():
    # Read columns in the same order used by the SQL INSERT statement.
    input_path = Path("data/processed/monza_2024_race_stints.parquet")
    columns = [
        "season",
        "event_name",
        "session_name",
        "driver_number",
        "stint_number",
        "compound",
        "recorded_laps",
        "first_lap",
        "last_lap",
    ]
    stints = pd.read_parquet(input_path, columns=columns)

    if stints.empty:
        raise ValueError("No processed stint records were found.")

    # Detect duplicate business keys before sending records to PostgreSQL.
    key = [
        "season",
        "event_name",
        "session_name",
        "driver_number",
        "stint_number",
    ]
    if stints.duplicated(key).any():
        raise ValueError("Duplicate stint keys were found.")

    records = list(stints.itertuples(index=False, name=None))

    insert_sql = """
        INSERT INTO staging.stints AS target (
            season, event_name, session_name, driver_number,
            stint_number, compound, recorded_laps, first_lap, last_lap
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT stints_pkey DO UPDATE SET
            compound = EXCLUDED.compound,
            recorded_laps = EXCLUDED.recorded_laps,
            first_lap = EXCLUDED.first_lap,
            last_lap = EXCLUDED.last_lap
        WHERE (
            target.compound, target.recorded_laps,
            target.first_lap, target.last_lap
        ) IS DISTINCT FROM (
            EXCLUDED.compound, EXCLUDED.recorded_laps,
            EXCLUDED.first_lap, EXCLUDED.last_lap
        )
    """

    # The connection commits on success and rolls back on error.
    # The password comes from .env through uv; it is not stored in this file.
    with psycopg.connect(
        host="127.0.0.1",
        port=5433,
        dbname=os.getenv("F1_DB_NAME", "f1_analytics"),
        user="f1_admin",
        password=os.environ["POSTGRES_PASSWORD"],
    ) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(insert_sql, records)
            affected_rows = cursor.rowcount

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM staging.stints
                WHERE season = %s
                  AND event_name = %s
                  AND session_name = %s
                """,
                (2024, "Italian Grand Prix", "Race"),
            )
            total_rows = cursor.fetchone()[0]

    print(f"Processed stint records: {len(stints)}")
    print(f"Rows inserted or updated: {affected_rows}")
    print(f"Monza race rows in staging.stints: {total_rows}")


if __name__ == "__main__":
    main()
