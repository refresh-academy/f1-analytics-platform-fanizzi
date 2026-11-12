# F1 Analytics Platform

A data engineering portfolio project that combines a historical Formula 1
data warehouse with a near-real-time telemetry replay pipeline.

The project is developed as a learning and portfolio initiative within
Refresh Academy.

## Verified Local Environment

The project has been developed and run on an Intel Mac (`amd64`) with
macOS Monterey, Docker Desktop 4.41.2, and Docker Engine 28.1.1.
These versions describe the verified local setup, not minimum requirements
for other systems.

## Project Status

> Current phase: speed-window metrics verified for completed replays.
> Spark stored 18 windows covering 322 speed samples. SQL reconciliation,
> checkpoint restart, and same-ID republication passed locally.
> Next: validate speed-window metrics during a new replay.

The repository currently includes:

- [x] Git, private GitHub repository, Python 3.13, and uv
- [x] Initial repository structure
- [x] FastF1 extraction of the Monza 2024 race
- [x] Raw and processed Parquet datasets, kept outside version control
- [x] PostgreSQL staging and analytical warehouse for this race
- [x] Driver, session, lap, and stint models
- [x] Repeatable loads and SQL data-quality checks
- [x] Analytical queries for laps, stints, strategies, and quality flags
- [x] Verified rebuild in a separate local PostgreSQL database
- [x] Grafana dashboard with lap and stint tables, tyre-compound chart,
  and Leclerc-Piastri lap-time comparison
- [x] Grafana comparison of Leclerc and Hamilton using race-result positions
- [x] Interactive Grafana median-sector comparison with driver selectors
- [x] Kafka 4.2.2 broker in KRaft mode, verified locally with Docker Compose
- [x] OpenF1 raw telemetry sample for Leclerc, Monza 2024 lap 10
- [x] Kafka replay of the 647-event Leclerc lap 10 sample,
  verified by reading it back from the broker
- [x] Spark Structured Streaming inspection of a completed Kafka replay
- [x] Spark Structured Streaming inspection while the Kafka replay is in progress
- [x] TimescaleDB hypertable for replay telemetry
- [x] Spark-to-TimescaleDB writes for completed and in-progress replays
- [x] Duplicate handling verified by republishing the same replay
- [x] Grafana telemetry replay dashboard with replay selection
- [x] Live replay visualization and completed replay review
- [x] Spark five-second speed-window metrics for completed replays
- [x] SQL reconciliation, checkpoint restart, and republication checks for metrics
- [ ] Speed-window metrics verified during an in-progress replay
- [x] Grafana display of five-second speed mean, minimum, and maximum

On 2026-11-11, the replay at original pacing stored 647 events in
`f1_telemetry` across 18 nonempty micro-batches. SQL confirmed 322 car
telemetry events and 325 position events. A separate test on 2026-11-10 republished
the same replay ID and inserted zero additional rows. The primary key
combines replay ID, event time, and event ID to identify repeated samples
within each replay.

The rebuild used `f1_analytics_smoke` in the same PostgreSQL container.
All five SQL quality checks passed, and repeating the loads changed
no rows. A rebuild on another computer has not yet been tested.

The current race snapshot contains **1,008 laps from 20 drivers** and
**50 stints**. FastF1 marks 927 laps with `IsAccurate=True` and 81 with
`IsAccurate=False`; a False flag does not by itself mean that a lap time
is wrong or deleted. Race-control deletion information was unavailable
when this snapshot was extracted.

See [the local run order](docs/run_order.md) for build commands and
[the data-quality notes](docs/monza_2024_data_quality.md) for the
observed limitations.

## Project Overview

The platform processes Formula 1 data through two complementary workflows.

1. A batch pipeline for historical analysis.
2. A streaming pipeline that replays historical telemetry as a live event stream.

The batch pipeline organizes sessions, drivers, laps, sector times, stints,
tyre compounds, and race results in PostgreSQL.

The streaming pipeline publishes historical telemetry samples through Kafka
at controlled intervals. Spark Structured Streaming writes them to TimescaleDB.
Grafana visualizes the replay from TimescaleDB. A separate Spark job
calculates five-second speed metrics for completed replays. Grafana displays
their means, minima, and maxima. Validation during publication is next.

## Project Goals

- Extract historical Formula 1 data with FastF1 and OpenF1.
- Preserve source data in Parquet format.
- Build reproducible and idempotent data pipelines.
- Design an analytical model for sessions, drivers, laps, and stints.
- Store analytical data in PostgreSQL and time-series data in TimescaleDB.
- Replay historical telemetry events through Apache Kafka.
- Process event streams with Spark Structured Streaming.
- Visualize historical and near-real-time metrics with Grafana.
- Run the infrastructure locally with Docker Compose.
- Document architectural decisions, data quality rules, and known limitations.

## Data Sources

The batch warehouse uses a previously acquired FastF1 snapshot of Monza
2024. The replay sample uses OpenF1 car telemetry and positions for
Leclerc, lap 10, from the same race. Separate raw Parquet files and a
local manifest preserve the sample's source and extraction details.

New FastF1 archive downloads require authenticated access; see the
[FastF1 archive access update](https://github.com/theOehrly/Fast-F1/issues/978).
The OpenF1 sample was acquired through its historical API.

The streaming component uses historical replay. Previously recorded telemetry
samples are published at controlled intervals to simulate data arriving from
a car during a session.

Each stored event preserves two timestamps.

- **Event time (`event_time`)** records when the sample occurred in the historical session.
- **Publication time (`published_at`)** records when the producer published the sample during replay.

## Telemetry Replay Dashboard

The [local telemetry dashboard](http://localhost:3000/d/monza-2024-telemetry-replay/monza-2024-telemetry-replay)
reads TimescaleDB through a dedicated read-only role. It includes:

- Stored event counts for the selected replay.
- Leclerc's speed in km/h against seconds since the first car telemetry event.
- Stacked publication counts in five-second buckets, split into car telemetry
  events and position events.

One car telemetry event is a timestamped measurement record with fields such
as speed, RPM, throttle, brake, and gear. One position event records spatial
coordinates. The sample contains 322 car telemetry events and 325 position
events for one driver.

The speed curve uses historical `event_time`. The publication chart groups
stored events by `published_at` and follows the dashboard time picker.
Counters and the speed curve cover the full selected replay. Publication
buckets describe when stored events were published; they do not measure
Spark processing time or end-to-end latency. These SQL buckets are separate
from Spark's event-time speed-window metrics.

For a running demo, use **Latest replay (auto)**, **Last 5 minutes**, and a
five-second refresh. Each replay is finite and lasts about 84 seconds at
original pacing. Grafana refresh, Spark's processing trigger, and the SQL
bucket width are three independent settings, each currently five seconds.

To review a completed demo, select its Replay ID and an absolute time range
covering its publication timestamps. Automatic refresh can be turned off.
An empty time range produces **No data** in the publication chart; the stored
events remain in TimescaleDB. SQL publication timestamps are shown in UTC in
the verified setup, while the dashboard uses the browser's time zone.

See [the run order](docs/run_order.md) for setup and replay commands. Dashboard
queries are versioned under `sql/grafana_telemetry_*.sql`; the builder is
`grafana/build_telemetry_dashboard.py`.

## Five-Second Speed Metrics

`src/streaming/aggregate_monza_2024_stream.py` reads one replay from Kafka
and groups car telemetry by five-second historical event-time windows,
replay ID, session, and driver. It stores the sample count and speed mean,
minimum, and maximum in `public.telemetry_speed_5s` in TimescaleDB.
The mean is an arithmetic sample mean, not a time-weighted or whole-lap mean.
Position events and missing speed values do not contribute.

Spark retains unique `(event_id, speed)` pairs within each active window
to avoid counting repeated source samples. Update mode writes the latest
known aggregate values, including the final windows of a finite replay.
Stored rows can be updated as more samples arrive; their presence does
not imply that the watermark has finalized every window.

The ten-second watermark follows the maximum historical event time seen
by the query. Older observations can be excluded from the metrics.
Window state grows with the unique samples in each active window; this
approach is intended for the current small replay. The metrics query has
its own checkpoints, separate from the raw-event writer and inspection.

On 2026-11-12, the completed-replay test stored **18 event-time windows**
covering **322 speed samples**. The independent SQL check in
`tests/sql/check_monza_speed_windows.sql` found no differences in window
coverage, interval width, sample counts, means, minima, or maxima.
Restarting from the same checkpoint and republishing the same Replay ID
both preserved these results. The republication run emitted three windows
and changed zero stored rows.

Grafana displays these metrics in **Speed | 5-second mean, min and max**.
Hover over the information icon beside the title for the panel description,
or over a point for its values. Validation during a new replay is next.

## Planned Architecture

```mermaid
flowchart TD
    A[FastF1 historical data] --> B[Python batch extraction]
    B --> C[Parquet raw storage]
    C --> D[PostgreSQL and TimescaleDB]
    D --> E[Grafana]

    I[OpenF1 historical telemetry] --> J[Python telemetry extraction]
    J --> K[Parquet telemetry sample]
    K --> F[Python telemetry replay]
    F --> G[Apache Kafka]
    G --> H[Spark Structured Streaming]
    H --> D
```

## Delivery Strategy

The project will be implemented incrementally.

### Phase 1: Project Foundation

- Configure Git and GitHub.
- Configure Python and uv.
- Create the repository structure.
- Document the initial architecture.

### Phase 2: Historical Data Pipeline

- Extract one Formula 1 session.
- Inspect source columns and data types.
- Store raw data in Parquet format.
- Add validation and data quality checks.

### Phase 3: Analytical Data Warehouse

- Define table grain and business keys.
- Create dimension and fact tables.
- Load PostgreSQL without generating duplicates.
- Write analytical SQL queries.

### Phase 4: Visualization

- Connect Grafana to the analytical database with a read-only PostgreSQL
  role (verified locally).
- Build lap, stint, sector, and driver comparison dashboards (lap and
  stint tables, compound chart, and two-driver lap-time plot complete;
  race-result comparison and interactive sector medians complete).

### Phase 5: Telemetry Replay

- Publish historical telemetry events through Kafka (verified locally).
- Process events with Spark Structured Streaming (verified locally).
- Store replay telemetry in TimescaleDB (verified locally).
- Visualize event counts, speed, and publication buckets in Grafana
  (verified locally).
- Calculate five-second speed-window metrics in Spark (verified locally
  for completed replays).
- Store calculated metrics in TimescaleDB (verified locally).
- Display speed-window means, minima, and maxima in Grafana (verified locally).
- Validate speed-window metrics during publication (planned).

### Phase 6: Reliability and Documentation

- Test restart and recovery behavior.
- Validate idempotent batch loads.
- Document operational commands and troubleshooting steps.
- Add dashboard screenshots or an animated demonstration.

## Planned Technology Stack

| Area | Technology |
|---|---|
| Data sources | FastF1 (batch), OpenF1 (telemetry sample) |
| Programming language | Python |
| Python environment | uv |
| Raw storage | Parquet |
| Analytical database | PostgreSQL |
| Time-series database | TimescaleDB |
| Message broker | Apache Kafka |
| Stream processing | Apache Spark Structured Streaming |
| Visualization | Grafana |
| Infrastructure | Docker Compose |
| Database client | DBeaver |
| Development environment | Visual Studio Code |

## Development Principles

- Build and verify one component at a time.
- Keep raw data separate from transformed data.
- Define the grain of every analytical table.
- Make repeated pipeline executions safe.
- Store credentials outside version control.
- Document technical decisions and data limitations.
- Add technologies only when they have a clear architectural role.

## Author

Vito Enrico Fanizzi
