"""Load processed Monza driver details into PostgreSQL staging."""

import os
from pathlib import Path

import pandas as pd
import psycopg


def main():
    input_path = Path("data/processed/monza_2024_race_drivers.parquet")
    columns = [
        "season",
        "event_name",
        "session_name",
        "driver_number",
        "driver_id",
        "abbreviation",
        "full_name",
        "team_name",
    ]
    drivers = pd.read_parquet(input_path, columns=columns)

    if drivers.empty:
        raise ValueError("No processed driver records were found.")

    # Each tuple follows the same column order as the INSERT statement.
    records = list(drivers.itertuples(index=False, name=None))

    insert_sql = """
        INSERT INTO staging.drivers AS target (
            season, event_name, session_name, driver_number,
            driver_id, abbreviation, full_name, team_name
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT drivers_pkey DO UPDATE SET
            driver_id = EXCLUDED.driver_id,
            abbreviation = EXCLUDED.abbreviation,
            full_name = EXCLUDED.full_name,
            team_name = EXCLUDED.team_name
        WHERE (
            target.driver_id, target.abbreviation,
            target.full_name, target.team_name
        ) IS DISTINCT FROM (
            EXCLUDED.driver_id, EXCLUDED.abbreviation,
            EXCLUDED.full_name, EXCLUDED.team_name
        )
    """

    # The connection context commits on success and rolls back on error.
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
            cursor.execute("SELECT COUNT(*) FROM staging.drivers")
            total_rows = cursor.fetchone()[0]

    print(f"Processed driver records: {len(drivers)}")
    print(f"Rows inserted or updated: {affected_rows}")
    print(f"Rows currently in staging.drivers: {total_rows}")


if __name__ == "__main__":
    main()
