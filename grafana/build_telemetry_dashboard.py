"""Build the Monza telemetry dashboard from its SQL queries."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_FILE = ROOT / "dashboards" / "monza_2024_telemetry_replay.json"


def main() -> None:
    # The provisioning file gives this connection the same UID on each setup.
    datasource = {
        "type": "grafana-postgresql-datasource",
        "uid": "f1_telemetry_timescaledb",
    }
    options_query = (ROOT / "sql/grafana_telemetry_replay_options.sql").read_text(
        encoding="utf-8"
    )
    counts_query = (ROOT / "sql/grafana_telemetry_replay_counts.sql").read_text(
        encoding="utf-8"
    )
    speed_query = (ROOT / "sql/grafana_telemetry_speed.sql").read_text(
        encoding="utf-8"
    )
    publications_query = (ROOT / "sql/grafana_telemetry_publications.sql").read_text(
        encoding="utf-8"
    )

    speed_windows_query = (ROOT / "sql/grafana_telemetry_speed_windows.sql").read_text(
        encoding="utf-8"
    )

    dashboard = {
        "uid": "monza-2024-telemetry-replay",
        "title": "Monza 2024 | Telemetry Replay",
        "tags": ["f1", "monza-2024", "telemetry"],
        "timezone": "browser",
        # Publication counts use the time picker, alongside full-replay views.
        "timepicker": {"hidden": False},
        "time": {"from": "now-5m", "to": "now"},
        "refresh": "5s",
        "schemaVersion": 41,
        "version": 0,
        "templating": {
            "list": [{
                "name": "telemetry_replay",
                "label": "Telemetry replay",
                "type": "query",
                "datasource": datasource,
                "definition": options_query,
                "query": options_query,
                "current": {"text": "Latest replay (auto)", "value": "latest"},
                "options": [],
                "refresh": 1,
                "hide": 0,
                "multi": False,
                "includeAll": False,
                "sort": 0,
            }]
        },
        "panels": [{
            "id": 1,
            "title": "Stored events for the selected replay",
            "description": (
                "Counts refresh every five seconds. The complete Leclerc lap 10 "
                "sample contains 647 events: 322 car telemetry events and 325 position events."
            ),
            "type": "stat",
            "gridPos": {"h": 6, "w": 24, "x": 0, "y": 0},
            "datasource": datasource,
            "targets": [{
                "refId": "A",
                "datasource": datasource,
                "editorMode": "code",
                "rawQuery": True,
                "rawSql": counts_query,
                "format": "table",
            }],
            "fieldConfig": {
                "defaults": {
                    "unit": "short",
                    "decimals": 0,
                    "color": {"mode": "fixed", "fixedColor": "blue"},
                },
                "overrides": [],
            },
            "options": {
                "reduceOptions": {
                    "values": False,
                    "calcs": ["lastNotNull"],
                    "fields": "",
                },
                "orientation": "horizontal",
                "textMode": "value_and_name",
                "colorMode": "value",
                "graphMode": "none",
            },
        }],
    }

    # Add a growing speed curve below the replay counters.
    dashboard["panels"].append({
        "id": 2,
        "title": "Leclerc lap 10 | Speed over the replay sample",
        "description": (
            "Speed in km/h against seconds since the first car sample. "
            "Historical event time defines the horizontal axis. "
            "Newly stored samples appear at each five-second refresh."
        ),
        "type": "xychart",
        "gridPos": {"h": 12, "w": 24, "x": 0, "y": 6},
        "datasource": datasource,
        "targets": [{
            "refId": "A",
            "datasource": datasource,
            "editorMode": "code",
            "rawQuery": True,
            "rawSql": speed_query,
            "format": "table",
        }],
        "fieldConfig": {
            "defaults": {
                "unit": "velocitykmh",
                "decimals": 0,
                "min": 0,
                "color": {"mode": "fixed", "fixedColor": "red"},
                "custom": {
                    "show": "lines",
                    "lineWidth": 2,
                    "axisLabel": "Speed (km/h)",
                },
            },
            "overrides": [{
                "matcher": {"id": "byName", "options": "elapsed_seconds"},
                "properties": [
                    {"id": "unit", "value": "none"},
                    {"id": "decimals", "value": 1},
                    {"id": "custom.axisLabel", "value": "Time since first car sample (s)"},
                ],
            }],
        },
        "options": {
            "mapping": "auto",
            "series": [{}],
            "legend": {"showLegend": False},
            "tooltip": {"mode": "single"},
        },
    })

    # Count publications in fixed five-second intervals for the selected replay.
    dashboard["panels"].append({
        "id": 3,
        "title": "Replay publications per 5 seconds",
        "description": (
            "Stored events grouped by published_at in five-second buckets. "
            "Blue shows car telemetry and orange shows positions. "
            "This panel uses the time picker. Empty ranges show No data. "
            "Counters and the speed curve cover the full selected replay."
        ),
        "type": "timeseries",
        "gridPos": {"h": 10, "w": 24, "x": 0, "y": 18},
        "datasource": datasource,
        "targets": [{
            "refId": "A",
            "datasource": datasource,
            "editorMode": "code",
            "rawQuery": True,
            "rawSql": publications_query,
            "format": "time_series",
        }],
        "fieldConfig": {
            "defaults": {
                "unit": "short",
                "decimals": 0,
                "min": 0,
                "custom": {
                    "drawStyle": "bars",
                    "barAlignment": 0,
                    "fillOpacity": 80,
                    "lineWidth": 0,
                    "showPoints": "never",
                    "stacking": {"mode": "normal", "group": "A"},
                    "axisLabel": "Published events / 5 s",
                },
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "Car telemetry events"},
                    "properties": [
                        {"id": "color", "value": {"mode": "fixed", "fixedColor": "blue"}}
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "Position events"},
                    "properties": [
                        {"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}}
                    ],
                },
            ],
        },
        "options": {
            "legend": {
                "showLegend": True,
                "displayMode": "table",
                "placement": "bottom",
                "calcs": ["sum"],
            },
            "tooltip": {"mode": "multi", "sort": "none"},
        },
    })

    # Compare Spark's five-second speed aggregates on the historical lap timeline.
    dashboard["panels"].append({
        "id": 4,
        "title": "Speed | 5-second mean, min and max",
        "description": (
            "Spark's latest mean, minimum and maximum speed for each five-second "
            "historical event-time window. Points are plotted at window end, "
            "relative to the first car sample. The first and last windows may "
            "cover only part of the sample. This panel covers the full selected "
            "replay, independently of the dashboard time picker."
        ),
        "type": "xychart",
        "gridPos": {"h": 12, "w": 24, "x": 0, "y": 28},
        "datasource": datasource,
        "targets": [{
            "refId": "A",
            "datasource": datasource,
            "editorMode": "code",
            "rawQuery": True,
            "rawSql": speed_windows_query,
            "format": "table",
        }],
        "fieldConfig": {
            "defaults": {
                "unit": "velocitykmh",
                "decimals": 1,
                "min": 0,
                "custom": {
                    "show": "points+lines",
                    "pointSize": {"fixed": 4},
                    "lineWidth": 1,
                    "axisLabel": "Speed (km/h)",
                },
            },
            "overrides": [
                {
                    "matcher": {"id": "byName", "options": "elapsed_seconds"},
                    "properties": [
                        {"id": "unit", "value": "none"},
                        {"id": "decimals", "value": 1},
                        {"id": "custom.axisLabel", "value": "Time since first car sample (s)"},
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "Mean speed"},
                    "properties": [
                        {"id": "color", "value": {"mode": "fixed", "fixedColor": "blue"}},
                        {"id": "custom.lineWidth", "value": 3},
                        {"id": "custom.pointSize", "value": {"fixed": 6}},
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "Minimum speed"},
                    "properties": [
                        {"id": "color", "value": {"mode": "fixed", "fixedColor": "green"}},
                    ],
                },
                {
                    "matcher": {"id": "byName", "options": "Maximum speed"},
                    "properties": [
                        {"id": "color", "value": {"mode": "fixed", "fixedColor": "orange"}},
                    ],
                },
            ],
        },
        "options": {
            "mapping": "auto",
            "series": [{}],
            "legend": {"showLegend": True, "displayMode": "list", "placement": "bottom"},
            "tooltip": {"mode": "multi", "sort": "none"},
        },
    })

    # The existing file provider loads dashboard JSON from this directory.
    DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_FILE.write_text(
        json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Created {DASHBOARD_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
