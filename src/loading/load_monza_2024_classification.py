"""Load processed Monza 2024 race classification into PostgreSQL staging."""

import os
from pathlib import Path

import pandas as pd
import psycopg


def main() -> None:
    source = Path("data/processed/monza_2024_race_classification.parquet")
    columns = [
        "season", "event_name", "session_name", "driver_number",
        "result_position", "classified_position", "laps_completed", "status",
    ]
    results = pd.read_parquet(source, columns=columns)
    if results.empty:
        raise ValueError("No processed race results were found.")

    records = list(results.itertuples(index=False, name=None))
    insert_sql = """
        INSERT INTO staging.race_results AS target (
            season, event_name, session_name, driver_number,
            result_position, classified_position, laps_completed, status
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT ON CONSTRAINT race_results_pkey DO UPDATE SET
            result_position = EXCLUDED.result_position,
            classified_position = EXCLUDED.classified_position,
            laps_completed = EXCLUDED.laps_completed,
            status = EXCLUDED.status
        WHERE (
            target.result_position, target.classified_position,
            target.laps_completed, target.status
        ) IS DISTINCT FROM (
            EXCLUDED.result_position, EXCLUDED.classified_position,
            EXCLUDED.laps_completed, EXCLUDED.status
        )
    """

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
                SELECT COUNT(*) FROM staging.race_results
                WHERE season = 2024
                  AND event_name = 'Italian Grand Prix'
                  AND session_name = 'Race'
                """
            )
            total_rows = cursor.fetchone()[0]

    print(f"Processed race results: {len(results)}")
    print(f"Rows inserted or updated: {affected_rows}")
    print(f"Monza race results in staging: {total_rows}")


if __name__ == "__main__":
    main()
