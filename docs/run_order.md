# Monza 2024 Warehouse: Local Run Order

This guide describes how to build the current Monza 2024 warehouse from a
new PostgreSQL database. Run each step in order and stop if a command fails.
For a database built before the lap accuracy flag was added, use the
migration section below. An up-to-date database can run step 7 directly.

## 0. Start the environment

The ignored `.env` file must define `POSTGRES_PASSWORD`. Run commands from
the repository root.

```bash
uv sync
docker compose up -d postgres
docker compose exec -T postgres pg_isready -U f1_admin -d f1_analytics
```

PostgreSQL may need a few seconds to start. Repeat the readiness command
until it reports `accepting connections`.

For the SQL steps below, define this helper in the same terminal:

```bash
run_sql() {
    docker compose exec -T postgres psql -P pager=off \
        -U f1_admin -d "${F1_DB_NAME:-f1_analytics}" -v ON_ERROR_STOP=1 < "$1"
}
```

The helper only lasts for the current terminal session. By default,
SQL commands and Python loaders use `f1_analytics`. Set `F1_DB_NAME` in
the current terminal to use another database for both.

## Rebuild check in a separate database

This procedure was verified with the Monza 2024 snapshot. It creates
a second database in the same PostgreSQL container. First confirm that its name is unused:

```bash
docker compose exec -T postgres psql -P pager=off -U f1_admin -d postgres -c "SELECT datname FROM pg_database WHERE datname = 'f1_analytics_smoke';"
```

If the query returns no rows, create and select the test database:

```bash
docker compose exec -T postgres createdb -U f1_admin f1_analytics_smoke
export F1_DB_NAME=f1_analytics_smoke
```

Define `run_sql` as shown above in the same terminal. Before running
steps 1 through 7, verify the database selected by both tools:

```bash
docker compose exec -T postgres psql -P pager=off -U f1_admin -d "$F1_DB_NAME" -c 'SELECT current_database();'
uv run --env-file .env python -c 'import os; print("Loader database:", os.environ["F1_DB_NAME"])'
```

After reviewing the rebuild results, run `unset F1_DB_NAME` to return
to the default database in this terminal. Keep the test database until
its results have been reviewed.

The verified local rebuild produced 1 session, 20 driver identities,
20 session-driver records, 1,008 lap facts, and 50 stint facts. All
five SQL quality checks and four analysis queries completed. Repeating
the three staging loaders and five warehouse loads changed no rows.
The original `f1_analytics` database still contained 1,008 lap facts
and 50 stint facts. This does not verify setup on another computer.

## 1. Extract source data

```bash
uv run python src/extraction/extract_monza_2024_laps.py
uv run python src/extraction/extract_monza_2024_results.py
```

These commands save raw Parquet files outside version control.

## 2. Validate and transform

```bash
uv run python src/transformation/validate_monza_2024_laps.py
uv run python src/transformation/transform_monza_2024_laps.py
uv run python src/transformation/transform_monza_2024_results.py
uv run python src/transformation/transform_monza_2024_stints.py
```

The transformed Parquet files are also generated locally and ignored by Git.

## 3. Create and load staging tables

Create the tables before running the Python loaders:

```bash
run_sql sql/create_staging_laps.sql
run_sql sql/create_staging_drivers.sql
run_sql sql/create_staging_stints.sql
```

Load the processed Parquet files:

```bash
uv run --env-file .env python src/loading/load_monza_2024_laps.py
uv run --env-file .env python src/loading/load_monza_2024_drivers.py
uv run --env-file .env python src/loading/load_monza_2024_stints.py
```

## 4. Create and load dimensions

The session comes from staged laps; driver identities come from staged
driver details.

```bash
run_sql sql/create_dim_session.sql
run_sql sql/load_dim_session.sql
run_sql sql/create_dim_driver.sql
run_sql sql/load_dim_driver.sql
```

## 5. Link drivers to the session

This table records each driver's race number and team in this session.

```bash
run_sql sql/create_session_driver.sql
run_sql sql/load_session_driver.sql
```

## 6. Create and load lap and stint facts

The driver foreign key can be added after session participation exists.
Create the fact tables and constraints before loading their rows.

```bash
run_sql sql/create_fact_lap.sql
run_sql sql/create_fact_stint.sql
run_sql sql/add_fact_lap_driver_fkey.sql
run_sql sql/load_fact_lap.sql
run_sql sql/load_fact_stint.sql
```

## 7. Check and explore the result

The first check compares lap and stint counts for each Monza driver.
The second verifies that each lap belongs to exactly one stint range
with the same compound. The third checks the observed missing sector
times. The fourth compares each complete lap time with its sector sum.
The fifth compares FastF1 accuracy flags between staging and the warehouse.
All five checks fail when their assertions fail.
The four summary queries display recorded laps, individual stints,
each driver's compound sequence, and FastF1 timing-quality flags.

```bash
run_sql tests/sql/check_monza_stint_lap_counts.sql
run_sql tests/sql/check_monza_stint_lap_assignments.sql
run_sql tests/sql/check_monza_sector_completeness.sql
run_sql tests/sql/check_monza_sector_sum.sql
run_sql tests/sql/check_monza_lap_accuracy.sql
run_sql sql/driver_lap_summary.sql
run_sql sql/driver_stint_summary.sql
run_sql sql/driver_strategy_summary.sql
run_sql sql/driver_lap_accuracy_summary.sql
```

The checks expect 20 drivers, 1,008 total laps, 988 laps with all sector
times, 927 True and 81 False values for the FastF1 is_accurate flag,
and the observed missing sector values. These expectations describe
this specific race snapshot.

## Update an existing database with lap accuracy

Use this sequence only for a database created before the accuracy
column was added. Start PostgreSQL and define `run_sql` as in step 0.
The migration scripts add nullable columns first; the loaders fill
them with source values before the `NOT NULL` constraints are applied.

```bash
uv run python src/transformation/transform_monza_2024_laps.py
run_sql sql/add_staging_lap_accuracy.sql
uv run --env-file .env python src/loading/load_monza_2024_laps.py
run_sql sql/require_staging_lap_accuracy.sql
run_sql sql/add_fact_lap_accuracy.sql
run_sql sql/load_fact_lap.sql
run_sql sql/require_fact_lap_accuracy.sql
run_sql tests/sql/check_monza_lap_accuracy.sql
```

A new database uses the updated `create_staging_laps.sql` and
`create_fact_lap.sql` definitions in the main run order; it does
not need the add-column migration scripts.

## Optional source exploration

These scripts help inspect the source but are not required to build the
warehouse:

```bash
uv run python src/extraction/inspect_monza_2024.py
uv run python src/transformation/profile_monza_2024_laps.py
```
