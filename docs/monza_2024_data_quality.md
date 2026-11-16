# Monza 2024 Race: Data Quality Notes

## Source and scope

The batch source is the 2024 Italian Grand Prix race loaded with FastF1 3.8.3.
The raw lap extraction contains 1,008 records for 20 drivers. Raw Parquet
files preserve the extracted source values and are not committed to Git.

## Observed checks

| Check | Result |
|---|---:|
| Lap records | 1,008 |
| Drivers with lap records | 20 |
| Missing lap times | 0 |
| Duplicate driver/lap keys | 0 |
| Missing first-sector times | 20, all on lap 1 |
| Laps marked `IsAccurate=True` | 927 |
| Laps marked `IsAccurate=False` | 81 |
| Laps marked `FastF1Generated=True` | 0 |

The missing first-sector times remain NULL in PostgreSQL. They are not
replaced with zero.

## Race-control information

The original extraction did not request race-control messages. A later
read-only attempt with `messages=True` failed with a FastF1
`SessionNotAvailableError` while fetching those messages. Consequently,
`Deleted` is `None` for all 1,008 extracted laps and `DeletedReason` is empty.
This does not establish that no lap times were deleted.

FastF1's `IsAccurate` flag concerns basic timing-data checks, including
the synchronization of lap boundaries. `IsAccurate=False` does not by
itself mean that the recorded lap time is wrong or was deleted.

## Analytical interpretation

The driver summary reports `minimum_recorded_lap_seconds`: the minimum
recorded lap time per driver in the loaded data. It is not labelled as an
official fastest-lap result because deletion information is unavailable.

All 20 per-driver minimum laps have `IsAccurate=True`, and none has a
`PitInTime` or `PitOutTime` value. These checks do not resolve the missing
race-control information.

If race-control messages become available, extract a separate source
snapshot, compare it with the current data, and review the transformation
rules before changing warehouse results.

## OpenF1 sample for telemetry replay

A separate OpenF1 snapshot covers Leclerc (driver 16), lap 10, in the
same Monza 2024 race (session 9590). Its lap duration is 84.432 seconds,
matching the FastF1 lap record. FastF1 telemetry and position requests
returned HTTP 401 during inspection on 2026-11-04.

The requested UTC window is 2024-09-01T13:16:21.155000+00:00 to
2024-09-01T13:17:45.587000+00:00. OpenF1 describes lap start times as
approximate, so this is a source-derived sampling window.

The saved snapshot contains 322 car samples and 325 position samples,
with counts checked against its manifest. Initial API inspection found
no missing required channel values, invalid timestamps, or duplicate
timestamps. Maximum observed gaps were 0.481 seconds for car data and
0.480 seconds for positions.

The two streams retain their own timestamps and source fields in separate
Parquet files. No interpolation, resampling, or missing-value replacement
has been applied. These checks do not prove every measurement is accurate.
Position coordinates are approximate. Kafka sample publishing and
read-back verification are implemented.

## Kafka replay verification

On 2026-11-05, the complete sample replay was acknowledged by Kafka and
read back from partition 0, offsets 4 through 650. The replay ID was
`d8afc0b0-8795-49cd-a3aa-948accf997e4`.

All 647 events matched the locally prepared events: 322 car samples and
325 positions. The checks covered message keys, replay ID, source payloads,
event IDs, and chronological ordering.

The first-to-last event-time span was 84.135 seconds; the corresponding
producer publication-time span was 84.139 seconds. These observations
describe this run and do not measure individual event latency.

The verification above covers the local single-broker sample replay
tested on 2026-11-05. Subsequent pipeline checks are summarized below.

## Streaming storage and speed-window validation

On 2026-11-16, replay `88b5ab88-949e-46e8-9eba-50ff302b4efc` was published
at original pacing while raw-event storage and speed aggregation ran as
independent queries in one Spark session. Kafka acknowledged 647 events
in partition 0, at offsets 6474 through 7120.

| Check | Result |
|---|---:|
| Stored raw events | 647 |
| Stored car telemetry events | 322 |
| Stored position events | 325 |
| Expected / stored five-second windows | 18 / 18 |
| Expected / stored speed samples | 322 / 322 |
| Mismatched windows | 0 |

The independent [SQL reconciliation](../tests/sql/check_monza_speed_windows.sql)
groups stored car telemetry with epoch-aligned five-second intervals.
It compares window coverage, interval ends, sample counts, means, minima,
and maxima. The comparison passed, using a mean-speed tolerance of
`1e-9` km/h.

Grafana's speed-window panel was observed updating during publication.
The screenshots linked from the README show the completed replay.

Event storage and metric updates commit independently. Grafana can refresh
between those commits, so final reconciliation must wait for both queries
to process the published events.

The metrics use historical event time and arithmetic sample means.
Stored rows contain the latest-known aggregates; their presence does not
mean every window has been finalized by the ten-second event-time watermark.

These results establish consistency between stored raw events and computed
metrics for this sample. They do not independently establish the accuracy
of the source measurements or remove the sampling limitations noted above.

See the [local run order](run_order.md) for commands, observed resource
usage, coordinator checks, and remaining verification limits.

## Reference

- [FastF1 lap timing field definitions](https://github.com/theOehrly/Fast-F1/blob/main/docs/api_reference/timing_data.rst)

- [OpenF1 API documentation](https://openf1.org/docs/)
