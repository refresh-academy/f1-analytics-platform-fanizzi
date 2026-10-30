# F1 Analytics Platform

A data engineering portfolio project that combines a historical Formula 1
data warehouse with a near-real-time telemetry replay pipeline.

The project is developed as a learning and portfolio initiative within
Refresh Academy.

## Project Status

> Current phase: Grafana visualization of the verified Monza 2024
> batch warehouse.

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
- [ ] Further Grafana views for sectors
- [ ] Kafka telemetry replay
- [ ] Spark Structured Streaming processing
- [ ] TimescaleDB telemetry storage

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

The platform will process Formula 1 data through two complementary workflows:

1. A batch pipeline for historical analysis.
2. A streaming pipeline that replays historical telemetry as a live event stream.

The batch pipeline will organize sessions, drivers, laps, sectors, stints,
compounds, and telemetry metadata into an analytical data warehouse.

The streaming pipeline will publish historical telemetry samples at controlled
intervals, process them with time-based calculations, and update live
visualizations.

## Project Goals

- Extract historical Formula 1 data with FastF1.
- Preserve source data in Parquet format.
- Build reproducible and idempotent data pipelines.
- Design an analytical model for sessions, drivers, laps, and stints.
- Store analytical data in PostgreSQL and time-series data in TimescaleDB.
- Replay historical telemetry events through Apache Kafka.
- Process event streams with Spark Structured Streaming.
- Visualize historical and near-real-time metrics with Grafana.
- Run the infrastructure locally with Docker Compose.
- Document architectural decisions, data quality rules, and known limitations.

## Data Source

The project uses FastF1 to access historical Formula 1 timing and telemetry
data.

Because public live Formula 1 telemetry APIs are limited, the streaming
component will use a historical replay approach. Previously recorded telemetry
samples will be published at controlled intervals to simulate data arriving
from a car during a session.

The replay will preserve two separate time concepts:

- **Event time:** when the telemetry sample occurred in the historical session.
- **Processing time:** when the sample is published and processed during replay.

## Planned Architecture

```mermaid
flowchart TD
    A[FastF1 historical data] --> B[Python batch extraction]
    B --> C[Parquet raw storage]
    C --> D[PostgreSQL and TimescaleDB]
    D --> E[Grafana]

    A --> F[Python telemetry replay]
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
  race-result comparison complete; sector views remain).

### Phase 5: Telemetry Replay

- Publish historical telemetry events through Kafka.
- Process events with Spark Structured Streaming.
- Calculate window-based metrics.
- Store telemetry and processed metrics in TimescaleDB.

### Phase 6: Reliability and Documentation

- Test restart and recovery behavior.
- Validate idempotent batch loads.
- Document operational commands and troubleshooting steps.
- Add dashboard screenshots or an animated demonstration.

## Planned Technology Stack

| Area | Technology |
|---|---|
| Data source | FastF1 |
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
