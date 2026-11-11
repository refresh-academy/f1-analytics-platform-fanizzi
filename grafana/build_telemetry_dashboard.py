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

    dashboard = {
        "uid": "monza-2024-telemetry-replay",
        "title": "Monza 2024 | Telemetry Replay",
        "tags": ["f1", "monza-2024", "telemetry"],
        "timezone": "browser",
        # Queries cover one complete replay and refresh while rows arrive.
        "timepicker": {"hidden": True},
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
                "sample contains 647 events: 322 car samples and 325 positions."
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

    # The existing file provider loads dashboard JSON from this directory.
    DASHBOARD_FILE.parent.mkdir(parents=True, exist_ok=True)
    DASHBOARD_FILE.write_text(
        json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Created {DASHBOARD_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
