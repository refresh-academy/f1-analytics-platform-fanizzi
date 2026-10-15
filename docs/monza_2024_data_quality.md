# Monza 2024 Race: Data Quality Notes

## Source and scope

The source is the 2024 Italian Grand Prix race loaded with FastF1 3.8.3.
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

## Reference

- [FastF1 lap timing field definitions](https://github.com/theOehrly/Fast-F1/blob/main/docs/api_reference/timing_data.rst)
