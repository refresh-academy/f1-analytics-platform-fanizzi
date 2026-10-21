# Monza 2024 Warehouse: Local Run Order

This guide describes how to build the current Monza 2024 warehouse from a
new PostgreSQL database. Run each step in order and stop if a command fails.
For an existing database, use the relevant checks and queries in step 7.

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
        -U f1_admin -d f1_analytics -v ON_ERROR_STOP=1 < "$1"
}
```

The helper only lasts for the current terminal session.

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
All four checks fail when their assertions fail.
The three summary queries display recorded laps, individual stints,
and each driver's compound sequence.

```bash
run_sql tests/sql/check_monza_stint_lap_counts.sql
run_sql tests/sql/check_monza_stint_lap_assignments.sql
run_sql tests/sql/check_monza_sector_completeness.sql
run_sql tests/sql/check_monza_sector_sum.sql
run_sql sql/driver_lap_summary.sql
run_sql sql/driver_stint_summary.sql
run_sql sql/driver_strategy_summary.sql
```

The checks expect 20 drivers, 1,008 total laps, 988 laps with all sector
times, and the observed missing sector values. These expectations describe
this specific race snapshot.

## Optional source exploration

These scripts help inspect the source but are not required to build the
warehouse:

```bash
uv run python src/extraction/inspect_monza_2024.py
uv run python src/transformation/profile_monza_2024_laps.py
```
