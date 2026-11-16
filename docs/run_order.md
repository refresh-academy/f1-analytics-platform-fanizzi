# Monza 2024 Warehouse: Local Run Order

This guide describes how to build the current Monza 2024 warehouse from a
new PostgreSQL database. Run each step in order and stop if a command fails.
For a database built before the lap accuracy flag was added, use the
migration section below. An up-to-date database can run step 7 directly.

The later sections cover Kafka replay, Spark inspection, TimescaleDB
storage, Grafana visualization, and event-time speed metrics for the
OpenF1 telemetry sample.

## 0. Start the environment

Run commands from the repository root. The versioned `.env.example`
lists the three database-password variables used by this project.
The populated `.env` remains local and ignored by Git.

For a new installation only, the following command creates `.env` from
the template and fills its password entries with generated values.
An existing `.env` is preserved.

If database volumes already exist but `.env` has been lost, recover the
original credentials instead. Changing environment values does not reset
passwords in initialized database volumes.

```bash
uv run --no-project python - <<'PY'
from pathlib import Path
import secrets

target = Path(".env")
if target.exists():
    print("Existing .env kept unchanged.")
else:
    content = Path(".env.example").read_text(encoding="utf-8")
    for name in [
        "POSTGRES_PASSWORD",
        "TIMESCALEDB_PASSWORD",
        "GRAFANA_TELEMETRY_PASSWORD",
    ]:
        expected = f"{name}=\n"
        if content.count(expected) != 1:
            raise SystemExit(f"Unexpected template entry: {name}")
        content = content.replace(
            expected, f"{name}={secrets.token_hex(24)}\n", 1
        )
    with target.open("x", encoding="utf-8") as output:
        output.write(content)
    print("Created local .env with generated database passwords.")
PY
```

`POSTGRES_PASSWORD` configures the batch database administrator.
`TIMESCALEDB_PASSWORD` configures the telemetry database administrator.
During the Grafana reader setup below, assign the value of
`GRAFANA_TELEMETRY_PASSWORD` to the `grafana_telemetry_reader` database role.
The Grafana web sign-in password is a separate credential.

With the local configuration available, start PostgreSQL:

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

Define `run_sql` as shown above in the same terminal. When reusing the
preserved raw snapshot, run steps 2 through 7 and skip the source-download
commands in step 1. Before loading, verify the database selected by both tools:

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

### Reuse an existing snapshot

The verified batch rebuild starts from these preserved raw files:

- `data/raw/monza_2024_race_laps.parquet`
- `data/raw/monza_2024_race_results.parquet`

If these files are available, continue with step 2. Transformation and
warehouse loading read them locally and do not request a new FastF1 download.

The streaming replay uses a separate preserved OpenF1 snapshot under
`data/raw/openf1_monza_2024_leclerc_lap_10/`, containing
`car_data.parquet`, `location.parquet`, and `manifest.json`.
Once acquired, publishing that replay does not require another API request.

Raw files, processed datasets, and caches are excluded from Git.
Keep a separate backup of the source snapshots, including the OpenF1
manifest. A ZIP produced by `git archive` contains versioned project files;
it does not back up those datasets, the local `.env`, database volumes,
or Spark checkpoints.

### Original batch acquisition path

The commands below document the original FastF1 acquisition path.
New timing-archive downloads require authenticated access. The current
scripts do not include an authentication setup, and fresh authenticated
acquisition has not been verified with this repository.
See the [README data sources](../README.md#data-sources).

The batch extraction scripts write their raw output paths directly.
Reuse existing snapshots for a rebuild rather than rerunning extraction
over the preserved files.

Original extraction commands:

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

Kafka carries the telemetry replay in the streaming pipeline. Kafka 4.2.2 runs
as one broker and KRaft controller in the `streaming` Compose profile.
The profile controls when it runs to conserve local memory; the `kafka_data`
volume persists across restarts. Sample publishing and read-back
verification are implemented. Spark can inspect replays and write them
to TimescaleDB, including while the producer is publishing.

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

## Replay and verify the telemetry sample

Start the services with the `streaming` profile as described above.
The following commands run from the repository root.

Prepare and inspect the 647 source events:
`uv run python src/transformation/prepare_monza_2024_replay.py`

Create the topic with one partition and one replica:
`docker compose --profile streaming exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:19092 --create --if-not-exists --topic f1.telemetry.raw.v1 --partitions 1 --replication-factor 1`

Publish the complete sample at its original pacing:
`uv run python -m src.streaming.replay_monza_2024 --speed 1`

The producer prints progress after broker acknowledgements. Record its
replay ID and first and last offsets. These values belong to that execution
and must not be copied unchanged from an earlier run.

Verify that execution by replacing REPLAY_ID, FIRST_OFFSET, and LAST_OFFSET:
`uv run python -m src.streaming.verify_monza_2024_replay --replay-id REPLAY_ID --start-offset FIRST_OFFSET --end-offset LAST_OFFSET`

The verifier expects all 647 events in a contiguous interval of partition 0.
It checks the replay ID, message keys, complete source payloads, event IDs,
and chronological ordering against the local snapshot.

Each event preserves its historical `event_time`. The producer adds a
`published_at` timestamp and generates a new `replay_id` by default.
Use `--replay-id` to select an explicit UUID. Running the producer again
publishes messages at new Kafka offsets. Source `event_id` values remain
stable, and the TimescaleDB writer deduplicates them within a replay.

Producer idempotence protects retries within one producer session.
It does not establish exactly-once processing across future consumers or
databases.

## Inspect a completed Kafka replay with Spark

Start Kafka with the `streaming` profile as described above. Build the
Spark image before its first use, and rebuild it after Dockerfile changes.

```bash
docker compose --profile processing build spark
```

From the repository root, replace `REPLAY_ID` with the ID of a completed replay.

```bash
docker compose run --rm spark \
  /opt/spark/app/inspect_monza_2024_stream.py \
  --replay-id REPLAY_ID
```

The job uses Spark Structured Streaming to read the available Kafka
records, print counts and example rows for the selected replay, and exit.
The local run for Leclerc's lap 10 counted 647 events, including 322 car
telemetry samples and 325 position samples.

The `spark_state` volume stores a separate checkpoint for each replay ID.
A second invocation for the same replay resumes from the saved offsets
and reports zero matching events when there are no new ones.

## Follow a Kafka replay with Spark

Start Kafka and open two terminals in the repository root. Generate a fresh
replay ID in terminal 2.

```bash
uv run python -c 'from uuid import uuid4; print(uuid4())'
```

In terminal 1, replace `REPLAY_ID` with that UUID and start Spark.

```bash
docker compose --profile streaming --profile processing run --rm spark \
  /opt/spark/app/inspect_monza_2024_stream.py \
  --follow --replay-id REPLAY_ID
```

Once Spark has started, use the same UUID in terminal 2 to publish the replay.

```bash
uv run python -m src.streaming.replay_monza_2024 \
  --speed 1 --replay-id REPLAY_ID
```

Watch the Spark batch counts while the producer publishes events. The local
test processed 647 events across 18 micro-batches, including 322 car telemetry
samples and 325 position samples.

After the replay finishes and Spark has displayed the final batch, press
Ctrl+C in terminal 1 to stop the inspection. Python may print
`KeyboardInterrupt` when the command is interrupted.

## Store telemetry replays in TimescaleDB

The `telemetry` profile provides TimescaleDB 2.31.0 on PostgreSQL 16.
Its database is `f1_telemetry`, its user is `f1_telemetry_admin`, and its
data is stored in `timescaledb_data`. Containers connect to
`timescaledb:5432` through the Compose network.

The ignored `.env` file must define a nonempty `TIMESCALEDB_PASSWORD`
alongside the existing `POSTGRES_PASSWORD`. The local setup generated
the telemetry password with `openssl rand -hex 24` and saved it in `.env`.
Keep both passwords private.

Start the four services and build the Spark image with these commands.

```bash
docker compose --profile streaming --profile telemetry up -d --wait \
  postgres grafana kafka timescaledb
docker compose --profile processing build spark
```

The Dockerfile installs `psycopg[binary]==3.3.6`, matching `uv.lock`.
Spark receives `TIMESCALEDB_PASSWORD` through `run --env` when the writer
is launched. The application code is mounted from `src/streaming`.

Define this SQL helper in each terminal where you run telemetry queries.

```bash
run_telemetry_sql() {
    docker compose --profile telemetry exec -T timescaledb sh -c \
        'PGPASSWORD="$POSTGRES_PASSWORD" psql -X -w -P pager=off -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 "$@"' \
        sh "$@"
}
```

Create the hypertable in a single transaction, then inspect its metadata.

```bash
run_telemetry_sql --single-transaction -f - < sql/create_telemetry_events.sql
run_telemetry_sql <<'SQL'
SELECT current_database() AS db, extversion
FROM pg_extension
WHERE extname = 'timescaledb';

SELECT hypertable_name, primary_dimension
FROM timescaledb_information.hypertables
WHERE hypertable_schema = 'public' AND hypertable_name = 'telemetry_events';
SQL
```

Expect `f1_telemetry | 2.31.0` and `telemetry_events | event_time`.
Each row represents one source event in one replay. The primary key is
`(replay_id, event_time, event_id)`, including the time partition column.
The typed measurements cover car data and position samples. Kafka topic,
partition, and offset identify the message from which each row was written.

### Write a completed replay

Use the saved OpenF1 snapshot and Kafka topic prepared above. In the same
terminal, generate a fresh UUID, publish the sample at 10x speed, and
process that replay with Spark.

```bash
f1_replay_id=$(uuidgen | tr '[:upper:]' '[:lower:]') &&
uv run python -m src.streaming.replay_monza_2024 \
  --speed 10 --replay-id "$f1_replay_id" &&
docker compose --profile streaming --profile processing --profile telemetry run \
  --rm --no-deps -T --env TIMESCALEDB_PASSWORD \
  spark /opt/spark/app/write_monza_2024_stream.py \
  --replay-id "$f1_replay_id"
```

The default writer processes the available Kafka backlog and exits.
It reuses `read_monza_replay` from the inspection script. Its checkpoints
live under `monza_timescale_v1/REPLAY_ID` in `spark_state`.
Each nonempty micro-batch is committed in one database transaction.
Logs report the received, inserted, and duplicate counts after that commit.

In the same terminal, check the selected replay.

```bash
run_telemetry_sql -v replay_id="$f1_replay_id" <<'SQL'
SELECT count(*) AS total,
       count(*) FILTER (WHERE event_type = 'car_data') AS car_data,
       count(*) FILTER (WHERE event_type = 'location') AS location
FROM public.telemetry_events
WHERE replay_id = :'replay_id'::uuid;
SQL
```

Expect `647 | 322 | 325` for this snapshot.

### Verify duplicate handling

Publish the same source events with the same replay ID, then rerun the
writer.

```bash
uv run python -m src.streaming.replay_monza_2024 \
  --speed 10 --replay-id "$f1_replay_id" &&
docker compose --profile streaming --profile processing --profile telemetry run \
  --rm --no-deps -T --env TIMESCALEDB_PASSWORD \
  spark /opt/spark/app/write_monza_2024_stream.py \
  --replay-id "$f1_replay_id"
```

Republishing creates new Kafka offsets, so Spark reads the events again.
The writer uses `ON CONFLICT (replay_id, event_time, event_id) DO NOTHING`.
For the complete repeated sample, the log totals must be 647 received,
0 inserted, and 647 duplicates. Repeat the SQL count query above and
expect `647 | 322 | 325`.

The local test on 2026-11-10 verified both the initial insert and this
duplicate test. A fresh replay ID stores a separate replay. Restarting
the writer with an up-to-date checkpoint resumes from saved offsets.

### Write while a replay is being published

Open two terminals in the repository root. In terminal 1, generate a
fresh UUID and start the writer in follow mode.

```bash
f1_live_replay_id=$(uuidgen | tr '[:upper:]' '[:lower:]') &&
docker compose --profile streaming --profile processing --profile telemetry run \
  --rm --no-deps --env TIMESCALEDB_PASSWORD \
  spark /opt/spark/app/write_monza_2024_stream.py \
  --follow --replay-id "$f1_live_replay_id"
```

Keep terminal 1 running. Follow mode uses a 5-second trigger and stores
its checkpoints under `monza_timescale_follow_v1/REPLAY_ID`.
The writer skips logging batches that contain no matching events.

In terminal 2, replace `REPLAY_ID` below with the UUID printed in
`Writing replay:` in terminal 1. Variables belong to the terminal
where they were set.

```bash
f1_live_replay_id=REPLAY_ID
uv run python -m src.streaming.replay_monza_2024 \
  --speed 1 --replay-id "$f1_live_replay_id"
```

Watch the `Batch` lines in terminal 1 during publication. Once the producer
has acknowledged 647 events and Spark has inserted the final batch,
define `run_telemetry_sql` in terminal 2 using the helper above, then run
the following query.

```bash
run_telemetry_sql -v replay_id="$f1_live_replay_id" <<'SQL'
SELECT count(*) AS total,
       count(*) FILTER (WHERE event_type = 'car_data') AS car_data,
       count(*) FILTER (WHERE event_type = 'location') AS location
FROM public.telemetry_events
WHERE replay_id = :'replay_id'::uuid;
SQL
docker stats --no-stream
```

Expect `647 | 322 | 325`. Record the memory measurement with its timing,
such as during publication or while the writer is waiting afterward.

The local test on 2026-11-11 used replay
`576439ac-8b3c-4682-a391-5f5c5562b4f9` at 1x speed. Kafka acknowledged
647 messages in partition 0, offsets 2592 through 3238. Spark inserted
all 647 events in 18 nonempty micro-batches, numbered 3 through 20,
with zero duplicates. SQL confirmed 322 car samples and 325 positions.

After that replay, with the follow writer waiting, Docker reported
622.3 MiB for Spark and 58.22 MiB for TimescaleDB. The five containers
used about 1.77 GiB in total. These values describe that waiting state.
At startup, one batch took 13.32 seconds against the 5-second trigger
interval. Processing then continued and completed the replay.

Each row preserves the original `event_time` and the replay's
`published_at`. The first supports analysis of the historical lap,
and the second records publication during the demo.

## Visualize telemetry replays in Grafana

Complete the TimescaleDB setup above first. Reuse the existing Grafana
account. Its sign-in password is separate from both database passwords.
The existing warehouse dashboard and telemetry dashboard share that account.

### Configure the telemetry data source once

The ignored `.env` must define a nonempty `GRAFANA_TELEMETRY_PASSWORD`.
This is the database password for `grafana_telemetry_reader`, not the
Grafana sign-in password or the TimescaleDB administrator password.

For a new setup, define `run_telemetry_sql` as shown above and create the
reader and its grants:

```bash
run_telemetry_sql --single-transaction -f - < sql/create_telemetry_grafana_reader.sql
```

On first setup, assign the same private value saved in
`GRAFANA_TELEMETRY_PASSWORD` at the password prompt, then enable login.
Skip these password commands when the reader is already configured.

```bash
docker compose --profile telemetry exec timescaledb sh -c \
  'PGPASSWORD="$POSTGRES_PASSWORD" psql -X -w -h 127.0.0.1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -c "\password grafana_telemetry_reader"'
run_telemetry_sql -c 'ALTER ROLE grafana_telemetry_reader LOGIN;'
```

`grafana/provisioning/datasources/telemetry.yaml` provisions the data source
with UID `f1_telemetry_timescaledb`. It connects to `timescaledb:5432`,
database `f1_telemetry`, as `grafana_telemetry_reader`. Compose passes
`GRAFANA_TELEMETRY_PASSWORD` to Grafana for expansion in that file.

Apply the provisioning configuration after saving the password in `.env`:

```bash
docker compose --profile telemetry config --quiet &&
docker compose up -d --no-deps --wait --wait-timeout 120 grafana
```

Once Grafana is ready, verify the data source using the existing Grafana
account. The second prompt is for that account's sign-in password.

```bash
printf 'Grafana username: '
read -r grafana_login &&
curl -sS --max-time 20 --user "$grafana_login" \
  --write-out '\nHTTP %{http_code}\n' \
  http://127.0.0.1:3000/api/datasources/uid/f1_telemetry_timescaledb/health
```

Expect `Database Connection OK`, status `OK`, and HTTP 200. If Grafana is
still starting and returns an empty reply, retry the health request once
startup has completed. The local permission check also confirmed SELECT
allowed and INSERT, UPDATE, and DELETE denied on `public.telemetry_events`.

### Generate and open the telemetry dashboard

```bash
run_telemetry_sql --single-transaction -f - < sql/create_telemetry_speed_5s.sql &&
run_telemetry_sql --single-transaction -f - < sql/grant_telemetry_speed_grafana_reader.sql &&
uv run --no-project python grafana/build_telemetry_dashboard.py &&
open 'http://localhost:3000/d/monza-2024-telemetry-replay/monza-2024-telemetry-replay'
```

The builder reads `sql/grafana_telemetry_*.sql` and writes
`dashboards/monza_2024_telemetry_replay.json`. The generated JSON is ignored
by Git. The existing file provider checks for changes about every 30 seconds.
After changing queries or the builder, regenerate the JSON, wait for the
provider, and reload the dashboard page.

The counters, raw speed curve, and speed-window panel cover the full
selected replay. The publication chart counts stored events by
`published_at` within the dashboard time range.
Blue represents car telemetry events and orange represents position events.
These events describe measurements for one driver, not different cars.

### Observe a raw-event replay in two terminals

This procedure starts only the event writer. For event storage and speed
metrics together, use the coordinated streaming replay section below.

Start PostgreSQL, Grafana, Kafka, and TimescaleDB with the four-service
command above. Open two terminals in the repository root. If a previous
follow writer is still running in terminal 1, stop it with Ctrl+C first.

In terminal 1, generate a fresh Replay ID and start the writer:

```bash
f1_live_replay_id=$(uuidgen | tr '[:upper:]' '[:lower:]') &&
docker compose --profile streaming --profile processing --profile telemetry run \
  --rm --no-deps --env TIMESCALEDB_PASSWORD \
  spark /opt/spark/app/write_monza_2024_stream.py \
  --follow --replay-id "$f1_live_replay_id"
```

Keep terminal 1 running. In terminal 2, open the dashboard for a new demo:

```bash
open 'http://localhost:3000/d/monza-2024-telemetry-replay/monza-2024-telemetry-replay?from=now-5m&to=now&var-telemetry_replay=latest'
```

Confirm **Latest replay (auto)**, **Last 5 minutes**, and a **5s** refresh
before publishing. The latest selection switches once the new replay has
stored events. The publication chart can initially show **No data**.

In terminal 2, run the following block. At the prompt, paste only the UUID
from `Writing replay:` in terminal 1, then press Enter:

```bash
printf 'Paste the new replay ID: '
read -r f1_demo_replay_id &&
uv run python -m src.streaming.replay_monza_2024 \
  --speed 1 --replay-id "$f1_demo_replay_id"
```

At 1x speed the sample takes about 84 seconds to publish. Watch the counters,
speed curve, and publication bars update as Spark stores incoming events.
The producer finishes after 647 acknowledgements; the follow writer keeps
waiting for more messages. Use a fresh UUID for another visual demo.

The three five-second settings have different purposes:

| Setting | Purpose |
|---|---|
| Spark processing trigger | Schedules micro-batch processing, subject to batch duration. |
| Grafana refresh | Queries the data source again for display. |
| Publication bucket width | Groups stored events by five-second publication intervals in SQL. |

The chart uses producer publication timestamps. It does not measure Spark
ingestion time, processing throughput, or end-to-end latency. Spark's
event-time speed windows are calculated by a separate query, which can
run alongside event storage in the coordinated procedure below.

### Verify and review the completed replay

After the producer finishes and Spark commits the final batch, define
`run_telemetry_sql` in terminal 2 as shown above and run:

```bash
run_telemetry_sql -v replay_id="$f1_demo_replay_id" <<'SQL'
SELECT COUNT(*) AS total,
       COUNT(*) FILTER (WHERE event_type = 'car_data') AS car_telemetry_events,
       COUNT(*) FILTER (WHERE event_type = 'location') AS position_events,
       MIN(published_at) AS first_published_at,
       MAX(published_at) AS last_published_at
FROM public.telemetry_events
WHERE replay_id = :'replay_id'::uuid;
SQL
```

Expect `647 | 322 | 325`. Select that Replay ID in Grafana and set an
absolute time range that includes both publication timestamps. SQL showed
UTC timestamps in the verified setup; Grafana uses the browser's time zone.
Automatic refresh can be set to **Off** when reviewing a completed replay.
Turning refresh off stops automatic queries; choosing the absolute time
range keeps the displayed interval fixed.

With **Last 5 minutes**, old publication bars eventually leave the visible
range. **No data** means no matching stored rows in the selected time range.
Changing the time range or refresh setting does not delete database rows.

The local demo on 2026-11-11 used Replay ID
`c7542b15-cd9f-437d-ac79-0d9915b9ecfa`. Kafka acknowledged all 647 events in
partition 0, offsets 4533 through 5179. SQL confirmed 322 car telemetry
events and 325 position events, published between
`2026-11-11 16:59:12.541116+00` and `2026-11-11 17:00:36.676648+00`.
That is 17:59:12 through 18:00:36 in Europe/Rome on that date.

This command opens an absolute range containing that verified replay:

```bash
open 'http://localhost:3000/d/monza-2024-telemetry-replay/monza-2024-telemetry-replay?from=1794416350000&to=1794416445000&var-telemetry_replay=c7542b15-cd9f-437d-ac79-0d9915b9ecfa'
```

The publication bars reappeared with totals of 322 and 325 after selecting
this range. This URL refers to that completed local demo. For a new demo,
use the relative-range URL above and a fresh Replay ID.

### Read the five-second speed panel

After running the metrics job, select its Replay ID in the dashboard.
The panel **Speed | 5-second mean, min and max** reads those Spark results.

Hover over the information icon (`i`) beside the panel title to read its
description. Hover over a plotted point to inspect the numeric speed values
for that window.

- **Mean (blue, thicker line):** arithmetic mean of the window's speed samples.
- **Minimum (green):** lowest sampled speed in that window.
- **Maximum (orange):** highest sampled speed in that window.

Each point summarizes a five-second historical event-time window. It is
positioned at the window end, measured in seconds since the first car sample.
The connecting lines link window summaries. The first and last windows may
contain samples from only part of their interval.

Displayed speeds are rounded to one decimal place; stored aggregates retain
their precision. This panel covers the full selected replay independently
of the dashboard time picker. The verified local replay contains 18 windows.
Use the metrics job in the next section to populate a selected replay.

## Calculate five-second speed-window metrics

This section covers the completed-replay validation. Start the four services
and build the Spark image as described above. The selected replay must still
be available in Kafka and already stored in `public.telemetry_events`, which
provides the independent SQL reference. Define `run_telemetry_sql` in this
terminal using the helper in the TimescaleDB section above.

### Create the metrics hypertable

```bash
run_telemetry_sql --single-transaction -f - < sql/create_telemetry_speed_5s.sql
```

`public.telemetry_speed_5s` stores one row per replay, session, driver, and
five-second window start. It contains the sample count and speed mean,
minimum, and maximum. Its time partition column is `window_start`, and the
primary key includes that column. Window starts are inclusive and ends are
exclusive. Only car telemetry events with non-null speed contribute.

The statistics use historical event time. Publication time and `updated_at`
have different meanings: the first records producer publication during the
replay, while the second records the metrics write transaction time.

### Define the job and validation helpers

Run these definitions in the same terminal used for the following checks:

```bash
run_speed_metrics() {
    docker compose --profile streaming --profile processing --profile telemetry run \
      --rm --no-deps -T --env TIMESCALEDB_PASSWORD \
      spark /opt/spark/app/aggregate_monza_2024_stream.py \
      --replay-id "$f1_metrics_replay_id"
}

check_speed_metrics() {
    run_telemetry_sql --single-transaction \
      -v replay_id="$f1_metrics_replay_id" -f - \
      < tests/sql/check_monza_speed_windows.sql
}
```

The metrics job reuses `read_monza_replay` and drains the available Kafka
records before exiting. Its offsets and aggregation state are stored under
`monza_speed_5s_v1/REPLAY_ID` in `spark_state`, separately from raw-event
storage and inspection. Application code is available through the existing
`src/streaming` bind mount.

Select a completed replay at the prompt, then run the calculation and check:

```bash
printf 'Paste a completed replay ID: '
read -r f1_metrics_replay_id &&
run_speed_metrics &&
check_speed_metrics
```

For the current sample, expect 18 expected and stored windows, 322 expected
and stored speed samples, zero mismatched windows, and
`Speed-window validation passed.`

The SQL test independently groups raw events with epoch-aligned `date_bin`.
It checks missing and unexpected windows, interval ends, sample counts,
minima, maxima, and sample means with a tolerance of `1e-9` km/h. It fails
for an empty raw reference or a disagreement. Its comparison table exists
only for the test transaction.

### Understand updates and the watermark

Spark retains distinct `(event_id, speed)` pairs in each active window.
Two different events with the same speed remain separate samples. An event
ID with conflicting speed values in the same window fails the calculation.
The mean is an arithmetic sample mean, not a time-weighted or whole-lap mean.

Update mode emits current aggregate values, including the last windows of
a finite replay. A row can be updated as more samples arrive. A stored row
does not by itself mean that the watermark has finalized that window.

The ten-second watermark follows the maximum historical event time observed
by the metrics query, not the current wall clock. Older observations can be
excluded. State size grows with unique samples in each active window, so
this design is intended for the current small replay.

The database writer replaces cumulative values in one transaction per batch.
It skips identical outputs and prevents a partial rebuild with fewer samples
from overwriting a more complete stored window. Log fields
`windows_received` and `windows_changed` describe that batch's emitted
windows and changed database rows. A window can appear in more than one
batch; sum `sample_count` in the table to count the stored speed samples.

### Verify restart and republication behavior

Run the same job again with the same Replay ID and checkpoint:

```bash
run_speed_metrics && check_speed_metrics
```

When there are no new matching events, there may be no `Metrics batch`
lines. The SQL result must remain 18 windows, 322 samples, and zero
mismatches for this snapshot.

Next, republish the same source events using the same Replay ID, then run
the job and SQL check again:

```bash
uv run python -m src.streaming.replay_monza_2024 \
  --speed 10 --replay-id "$f1_metrics_replay_id" &&
run_speed_metrics &&
check_speed_metrics
```

Kafka assigns new offsets to these messages. Older events can be excluded
by the watermark, and duplicates within active windows retain their existing
sample identity. The stored metrics must still match the raw reference.

### Observed local results

On 2026-11-12, replay `c7542b15-cd9f-437d-ac79-0d9915b9ecfa` produced
18 stored windows covering 322 speed samples. The first run emitted
13 windows in batch 4 and 6 in batch 5; one window appeared in both batches.
The independent SQL comparison passed for all 18 windows.

Restarting from the checkpoint preserved those results. After republishing
the same Replay ID, batch 7 emitted three windows and changed zero database
rows. The SQL check again reported 18 windows, 322 samples, and zero
mismatches. Startup messages about disabling AQE for stateful workloads and
loading state snapshots appeared in these successful runs.

The CLI also provides `--follow`, with checkpoint prefix
`monza_speed_5s_follow_v1` and a five-second processing trigger. Coordinated
event storage, speed aggregation, and Grafana speed-window updates during
publication were verified locally on 2026-11-16, as described below.

## Run the coordinated streaming replay

This procedure runs raw-event storage and five-second speed aggregation
in one Spark session. It was verified locally during publication on
2026-11-16 using the existing Monza 2024 sample.

### Prerequisites and terminal roles

Complete the Kafka topic, TimescaleDB tables, Grafana reader grants, data
source, and dashboard setup in the earlier sections. Keep the saved OpenF1
sample available locally. Define `run_telemetry_sql` in terminal 2 using
the helper from the TimescaleDB section.

Run all commands from the repository root in VS Code's integrated terminal.

| Terminal | Purpose |
|---|---|
| 1 | Run the coordinated Spark job and retain its output. |
| 2 | Start services, check offsets, publish the replay, and run SQL checks. |

The verified Docker budget is approximately 3.823 GiB. Spark uses
`local[1]`, a 512 MiB Java driver heap, and a 1.5 GiB container limit.
Use one Spark container for this demo. Stop an earlier follow job before
starting another one.

The two queries share the session but keep independent checkpoints and
database transactions. Their panels can update at different times.
The coordinator monitors both queries. A streaming exception, or an
unexpected normal query termination in follow mode, fails the job and
closes the shared session.

### Start services and the coordinated job

In terminal 2, start the four services:

```bash
docker compose --profile streaming --profile telemetry up -d --wait \
  postgres grafana kafka timescaledb
```

In terminal 1, generate a fresh Replay ID and start Spark:

```bash
f1_live_replay_id=$(uuidgen | tr '[:upper:]' '[:lower:]') &&
uv run --env-file .env --no-project docker compose \
  --profile streaming --profile processing --profile telemetry run \
  --no-deps \
  --name "f1-monza-${f1_live_replay_id}" \
  --env TIMESCALEDB_PASSWORD \
  spark /opt/spark/app/write_monza_2024_stream.py \
  --follow \
  --with-speed-metrics \
  --replay-id "$f1_live_replay_id"
```

`uv` loads the local `.env` for this command. The password is passed through
the environment rather than included in the command arguments.
Application code is bind-mounted; Python-only edits do not require an image
rebuild. Rebuild after changes to the Spark Dockerfile or its dependencies.

The container name includes the UUID so older diagnostic containers can be
retained without a naming conflict. The command omits `--rm` to preserve
logs and exit status after termination.

Wait for the following messages:

```text
Writing replay: <UUID>
Checkpoint: .../monza_timescale_follow_v1/<UUID>
Aggregating replay: <same UUID>
Checkpoint: .../monza_speed_5s_follow_v1/<same UUID>
Started queries: events, speed_metrics
```

These messages confirm query startup, not completion of backlog recovery.
Keep terminal 1 running.

### Check both checkpoints before publication

In terminal 2, paste only the UUID printed by Spark:

```bash
printf 'Paste the new replay ID: '
read -r f1_demo_replay_id &&
f1_demo_container="f1-monza-${f1_demo_replay_id}"
```

Variables set in terminal 1 are not automatically available in terminal 2.
Check memory and Kafka's end offsets:

```bash
docker stats --no-stream \
  --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}' &&
docker compose --profile streaming exec -T kafka \
  /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:19092 \
  --topic f1.telemetry.raw.v1 \
  --time -1
```

Read the source offsets of each query's latest completed batch:

```bash
docker exec -i "$f1_demo_container" python3 - "$f1_demo_replay_id" <<'PY'
import json
import sys
from pathlib import Path
from uuid import UUID

replay_id = str(UUID(sys.argv[1]))
root = Path("/opt/spark/work-dir/checkpoints")

for label, prefix in [
    ("events", "monza_timescale_follow_v1"),
    ("speed_metrics", "monza_speed_5s_follow_v1"),
]:
    checkpoint = root / prefix / replay_id
    commits = checkpoint / "commits"
    batch_ids = [
        int(path.name)
        for path in commits.iterdir()
        if path.is_file() and path.name.isdigit()
    ] if commits.is_dir() else []

    if not batch_ids:
        print(f"{label}: no completed micro-batch yet.")
        continue

    batch_id = max(batch_ids)
    lines = (checkpoint / "offsets" / str(batch_id)).read_text().splitlines()
    if len(lines) < 3 or lines[0] != "v1":
        raise SystemExit(f"Unexpected checkpoint format for {label}.")

    print(f"{label}: last_committed_batch={batch_id}")
    for source in lines[2:]:
        if source.strip():
            offsets = None if source == "-" else json.loads(source)
            print("Committed source offsets:", json.dumps(offsets, sort_keys=True))
PY
```

Before publishing, both queries must match Kafka's end offsets for every
partition. Batch numbers can differ. If a query has not caught up, leave it
running and repeat the checks. With no producer publishing, the end offsets
should remain stable. Kafka's end offset is the next message position,
rather than the offset of the last existing message.

New queries read Kafka from `earliest`, filtering for their Replay ID.
They must therefore scan older replays too. Empty matching batches do not
produce the usual event-write or metrics-write log lines.

### Prepare Grafana and publish at original pacing

In terminal 2, open the live dashboard:

```bash
open 'http://localhost:3000/d/monza-2024-telemetry-replay/monza-2024-telemetry-replay?from=now-5m&to=now&var-telemetry_replay=latest&refresh=5s'
```

Confirm **Latest replay (auto)**, **Last 5 minutes**, and refresh **5s**.
Make the fourth panel, **Speed | 5-second mean, min and max**, visible
before publishing. The dashboard can still display the previous replay
until the first events of the new one are stored.

Start the producer in terminal 2:

```bash
if [ "$(docker inspect --format '{{.State.Running}}' "$f1_demo_container")" = "true" ]; then
  uv run python -m src.streaming.replay_monza_2024 \
    --speed 1 \
    --replay-id "$f1_demo_replay_id"
else
  printf '%s\n' 'Stopped: the Spark container is not running.'
fi
```

The sample takes about 84 seconds at original pacing. Watch the event
counts, raw speed curve, publication bars, and speed-window curves.
The fourth panel should populate as speed samples are processed. A brief
empty panel is possible while the new replay's first aggregates are pending.

The producer should acknowledge all 647 events and print its first and
last broker positions. Record those positions for this execution.
Leave Spark running after the producer exits so both queries can finish
their remaining batches.

The five-second processing trigger, dashboard refresh, publication bucket
width, and event-time window width are independent settings. They do not
establish a five-second end-to-end latency guarantee.

### Reconcile stored events and speed windows

After the final batches, run in terminal 2:

```bash
run_telemetry_sql -v replay_id="$f1_demo_replay_id" <<'SQL'
SELECT COUNT(*) AS total_events,
       COUNT(*) FILTER (WHERE event_type = 'car_data') AS car_data_events,
       COUNT(*) FILTER (WHERE event_type = 'location') AS location_events,
       MIN(published_at) AS first_published_at,
       MAX(published_at) AS last_published_at
FROM public.telemetry_events
WHERE replay_id = :'replay_id'::uuid;
SQL

run_telemetry_sql --single-transaction \
  -v replay_id="$f1_demo_replay_id" -f - \
  < tests/sql/check_monza_speed_windows.sql
```

Expect 647 events, including 322 car telemetry events and 325 positions.
The speed-window test must report 18 expected and stored windows,
322 expected and stored samples, zero mismatched windows, and
`Speed-window validation passed.`

If processing is still in progress, wait for the remaining batches before
repeating the checks. Investigate a persistent disagreement.

The comparison independently calculates windows from stored raw events.
It checks coverage, interval ends, counts, means, minima, and maxima.
Update-mode rows remain latest-known aggregates; their presence does not
mean every window has been finalized by the watermark.

Record the container state and memory after verification:

```bash
docker inspect \
  --format 'status={{.State.Status}} exit_code={{.State.ExitCode}} oom_killed={{.State.OOMKilled}}' \
  "$f1_demo_container" &&
docker stats --no-stream \
  --format 'table {{.Name}}\t{{.MemUsage}}\t{{.CPUPerc}}'
```

For a running container, `exit_code=0` is not a completed-job result.
Record when each memory snapshot was taken.

### Review a completed streaming replay

Select its explicit Replay ID, choose an absolute range containing both
publication timestamps, and set refresh to **Off**.

With a relative range such as **Last 5 minutes**, the publication chart's
time boundaries advance during refresh. Refresh **Off** stops periodic
dashboard queries; it does not stop Spark, the producer, or database writes.
An absolute range fixes the publication chart's time boundaries.
Counters and both speed panels cover the selected replay independently
of that time picker.

### Observed coordinated replay on 2026-11-16

The visually observed test used container `f1-monza-live-observe`.
The procedure above derives container names from Replay IDs for future runs.

| Check | Observed result |
|---|---|
| Replay ID | `88b5ab88-949e-46e8-9eba-50ff302b4efc` |
| Producer pacing | 1x, original historical intervals |
| Kafka acknowledgements | 647 |
| Kafka partition and offsets | Partition 0, offsets 6474 through 7120 |
| Stored events | 647: 322 car telemetry and 325 position events |
| Expected / stored windows | 18 / 18 |
| Expected / stored speed samples | 322 / 322 |
| Mismatched windows | 0 |
| Grafana observation | Speed-window curves updated during publication |

Publication timestamps were `2026-11-16 11:58:23.800389+00` through
`2026-11-16 11:59:47.935592+00`, corresponding to
12:58:23.800389 through 12:59:47.935592 in Europe/Rome.

This URL opens that replay with a small margin around its publication:

```bash
open 'http://localhost:3000/d/monza-2024-telemetry-replay/monza-2024-telemetry-replay?from=1794830295000&to=1794830395000&var-telemetry_replay=88b5ab88-949e-46e8-9eba-50ff302b4efc'
```

Set refresh to **Off** for review. The fixed range is 11:58:15 through
11:59:55 UTC, or 12:58:15 through 12:59:55 in Europe/Rome.

After reconciliation, the container was still running with
`oom_killed=false`. Spark used 647.6 MiB of its 1.5 GiB limit.
The five running containers used approximately 1.89 GiB in total.
These are post-replay snapshots, not measured peaks during publication.

Completed streaming-replay screenshots are versioned alongside this guide:

- [Sample-level speed](screenshots/monza_2024_speed_samples.png)
- [Spark five-second speed windows](screenshots/monza_2024_speed_windows.png)

The screenshots show final results. Speed-window curves were observed
updating during publication in the same test.

### Verification limits and operational notes

Four simulated coordinator checks passed: waiting for both backlog
queries, detecting a metrics failure while events continued, rejecting
unexpected normal termination in follow mode, and detecting a failure
after the other query had completed. A forced-failure test of the complete
coordinated Spark runtime has not been performed.

Checkpoint restart and same-ID republication of completed-replay metrics
were verified on 2026-11-12. Those results do not establish recovery of the
complete coordinated pipeline after every kind of failure.

An earlier attempt on 2026-11-16 exited after repeated driver heartbeat
failures. Its initial cause was not established. Preserve the container
and full logs when investigating another unexpected exit.

Keep the Mac awake and avoid logout during the demonstration.
A native-Hadoop fallback warning and an AQE warning appeared in successful
runs. A `falling behind` warning means a batch exceeded the processing
trigger interval; check continued progress and query errors rather than
treating the trigger as a processing-time guarantee.

## Stop and restart the environment

After the final batch, stop any active follow job with Ctrl+C in its
terminal and wait for the prompt. Completed-replay jobs exit automatically.
The `--rm` option removes a one-off Spark container when it exits.
The coordinated procedure above omits that option so logs and exit status
remain available. After stopping that container, review its diagnostics
before removing it:

```bash
docker inspect \
  --format 'status={{.State.Status}} exit_code={{.State.ExitCode}} oom_killed={{.State.OOMKilled}}' \
  "$f1_demo_container"
docker logs --tail 60 "$f1_demo_container"
docker rm "$f1_demo_container"
```

These commands use the container variable from terminal 2 of the coordinated
procedure. A manual Ctrl+C can produce exit code 130. Removing the stopped
container preserves the named data and checkpoint volumes.

Check the remaining services.

```bash
docker compose --profile streaming --profile processing --profile telemetry ps --all
```

The local test confirmed that PostgreSQL, Grafana, Kafka, and TimescaleDB
remained running. TimescaleDB reported healthy.

Stop those services before shutting down the Mac with this command.

```bash
docker compose --profile streaming --profile telemetry stop
```

On a later day, open Docker Desktop with `open -a Docker`, wait for it
to be ready, then use the four-service startup command above. Compose
reuses the named volumes, including the telemetry data and checkpoints.
