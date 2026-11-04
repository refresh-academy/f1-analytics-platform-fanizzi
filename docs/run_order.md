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
uv run python src/transformation/transform_monza_2024_classification.py
uv run python src/transformation/transform_monza_2024_stints.py
```

The transformed Parquet files are also generated locally and ignored by Git.

## 3. Create and load staging tables

Create the tables before running the Python loaders:

```bash
run_sql sql/create_staging_laps.sql
run_sql sql/create_staging_drivers.sql
run_sql sql/create_staging_race_results.sql
run_sql sql/create_staging_stints.sql
```

Load the processed Parquet files:

```bash
uv run --env-file .env python src/loading/load_monza_2024_laps.py
uv run --env-file .env python src/loading/load_monza_2024_drivers.py
uv run --env-file .env python src/loading/load_monza_2024_classification.py
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

## 6. Create and load lap, stint, and race-result facts

The driver foreign key can be added after session participation exists.
Create the fact tables and constraints before loading their rows.

```bash
run_sql sql/create_fact_lap.sql
run_sql sql/create_fact_stint.sql
run_sql sql/create_fact_race_result.sql
run_sql sql/add_fact_lap_driver_fkey.sql
run_sql sql/load_fact_lap.sql
run_sql sql/load_fact_stint.sql
run_sql sql/load_fact_race_result.sql
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

## Connect Grafana to the local warehouse

Complete the warehouse build before this section. The Grafana reader is
created once in `f1_analytics`; do not run its creation script again if
the role already exists. Its `SELECT` grant covers the warehouse tables
that exist when the script runs.

```bash
docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 \
    -U f1_admin -d f1_analytics < sql/create_grafana_reader.sql
```

If `grafana_reader` already exists from an earlier build, skip its
creation script. Grant it access to the new race-result table instead:

```bash
docker compose exec -T postgres psql -X -v ON_ERROR_STOP=1 \
    -U f1_admin -d f1_analytics \
    -c "GRANT SELECT ON TABLE warehouse.fact_race_result TO grafana_reader;"
```

Set a private password interactively, then enable login. Do not put the
password in a script, Git, or the terminal command line.

```bash
docker compose exec postgres psql -X -U f1_admin \
    -d f1_analytics -c '\password grafana_reader'
docker compose exec postgres psql -X -v ON_ERROR_STOP=1 \
    -U f1_admin -d f1_analytics -c "ALTER ROLE grafana_reader LOGIN;"
```

Start Grafana and check its local health endpoint:

```bash
docker compose up -d grafana
curl -fsS http://127.0.0.1:3000/api/health
```

Open `http://127.0.0.1:3000`. On a new Grafana installation, sign in
with `admin` / `admin` and change the administrator password. Add a
PostgreSQL data source with these settings:

- Name: `f1_analytics_warehouse_fanizzi`
- Host URL: `postgres:5432` (the Docker network address)
- Database name: `f1_analytics`
- Username: `grafana_reader`
- Password: the private password set above
- TLS/SSL mode: `disable` for this local Docker network

Click **Save & test** to verify the connection. The Grafana administrator
password and the PostgreSQL reader password are separate credentials.
Grafana settings are stored in the persistent `grafana_data` Docker volume.

## Generate the dashboard

After saving the PostgreSQL data source, find its UID through Grafana's
local API. Replace `YOUR_GRAFANA_USERNAME` with your Grafana login name;
`curl` prompts for that account's password without putting it in the
command history.

```bash
curl -fsS -u YOUR_GRAFANA_USERNAME \
    http://127.0.0.1:3000/api/datasources |
    uv run python -c 'import json,sys; print([(d["name"], d["uid"]) for d in json.load(sys.stdin)])'
```

Use the UID shown for `f1_analytics_warehouse_fanizzi` to generate the
dashboard from the SQL queries in this repository:

```bash
uv run python grafana/build_dashboard.py --datasource-uid YOUR_DATASOURCE_UID
```

The generated `dashboards/monza_2024_driver_laps.json` is local and
ignored by Git because its data source UID belongs to this Grafana
installation. Grafana reads it through the file provider in
`grafana/provisioning/dashboards/warehouse.yaml`.
The upper panel stacks recorded lap counts for each driver by tyre
compound (HARD, MEDIUM, SOFT). Its horizontal scale counts laps;
coloured segments add to each driver's total and do not show race lap
numbers or stint order. Hover for exact values. Its query lives in
`sql/grafana_driver_compound_laps.sql`. The table below lists recorded
laps and minimum lap times; the minimum is not an official fastest-lap
result. The time picker is hidden because these queries describe a
fixed race.

The stint table shows one row per driver and stint, with inclusive
first and last race lap numbers. Repeated compounds remain separate.
The XY chart compares Leclerc and Piastri: race lap number is horizontal
and recorded lap time in seconds is vertical. It shows separate points
only for laps with FastF1 `IsAccurate=True` (50 of 53 for Leclerc and
48 of 53 for Piastri). Missing points are excluded by this basic
timing check, not proven wrong or deleted. Race-control deletion data
is unavailable, so the chart does not establish official fastest laps
or finishing positions. Its query is in
`sql/grafana_lap_time_comparison.sql`.

The race-result chart uses classified positions from the extracted
FastF1 results: Leclerc is first (the winner) and Hamilton is fifth.
A lower position number is better, even though its bar is shorter.
These positions are not calculated from the lap-time chart. The query
is in `sql/grafana_hamilton_leclerc_result.sql`.

The median sector chart has two dropdowns above the dashboard, labelled
`Sector chart only: Driver A` and `Sector chart only: Driver B`. They
affect only that chart; the other panels keep their fixed queries.
Each option shows the driver's number of usable laps. The default
comparison is Leclerc (50 laps) against Piastri (48 laps); Tsunoda
has only 5 usable laps in this snapshot.

The chart shows median sector times in seconds, rounded to three
decimals. It includes only laps with FastF1 `IsAccurate=True` and all
three sector times present. Small differences can be hard to see in
the bars, so hover for values. Tyres and traffic are not controlled
for; these medians are not official rankings. The calculation is in
`sql/grafana_sector_medians.sql`, and the dropdown options come from
`sql/grafana_sector_driver_options.sql`. The median query contains
Grafana variables and must be given driver values to run in `psql`.

To change this provisioned dashboard, edit its source query or builder
script, then regenerate the JSON. Grafana polls
for changes about every 30 seconds.

After Docker Desktop starts on later days, run `docker compose up -d`
from the repository root to start both PostgreSQL and Grafana. Use the
`pg_isready` command from step 0 if PostgreSQL needs time to accept
connections.

## Kafka broker for telemetry replay

Kafka is a core part of the planned streaming pipeline. Kafka 4.2.2 runs
as one broker and KRaft controller in the `streaming` Compose profile.
The profile controls when it runs to conserve local memory; the `kafka_data`
volume persists across restarts. Telemetry publishing and Spark processing
are not implemented yet.

After Docker Desktop starts, run `docker compose --profile streaming up -d`
from the repository root to start PostgreSQL, Grafana, and Kafka.
Check container status with `docker compose --profile streaming ps`.

## Extract the OpenF1 telemetry sample

The replay sample uses OpenF1 data for Leclerc, lap 10, from the same
Monza 2024 race. The batch warehouse uses the existing FastF1 snapshot.

From the repository root, run:
`uv run python src/extraction/extract_monza_2024_telemetry_sample.py`

The output directory is `data/raw/openf1_monza_2024_leclerc_lap_10/`.
It contains `car_data.parquet`, `location.parquet`, and `manifest.json`.
The manifest records the source, lap record, query window, extraction
time, and row counts. These local files are ignored by Git.

If the output directory already exists, the extractor stops to preserve
the snapshot. Keep that snapshot for replay rather than overwriting it.
See `docs/monza_2024_data_quality.md` for the observed checks and limitations.
