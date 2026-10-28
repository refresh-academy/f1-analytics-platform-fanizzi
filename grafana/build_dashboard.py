"""Build the Monza 2024 Grafana dashboard from the reviewed SQL query."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "sql" / "driver_lap_summary.sql"
DASHBOARD_FILE = ROOT / "dashboards" / "monza_2024_driver_laps.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--datasource-uid",
        required=True,
        help="UID of the local Grafana PostgreSQL data source",
    )
    args = parser.parse_args()

    # The SQL file remains the single source for this panel's query.
    query = SQL_FILE.read_text(encoding="utf-8")

    # Grafana assigns a data source UID per installation.
    datasource = {
        "type": "grafana-postgresql-datasource",
        "uid": args.datasource_uid,
    }

    dashboard = {
        "uid": "monza-2024-driver-laps",
        "title": "Monza 2024 | Driver Laps",
        "tags": ["f1", "monza-2024"],
        "timezone": "browser",
        "schemaVersion": 41,
        "version": 0,
        "panels": [
            {
                "id": 1,
                "title": "Recorded laps by driver",
                "description": (
                    "The minimum recorded lap is exploratory; "
                    "it is not an official fastest-lap result."
                ),
                "type": "table",
                "gridPos": {"h": 12, "w": 24, "x": 0, "y": 0},
                "datasource": datasource,
                "targets": [
                    {
                        "refId": "A",
                        "datasource": datasource,
                        "editorMode": "code",
                        "rawQuery": True,
                        "rawSql": query,
                        "format": "table",
                    }
                ],
                "options": {"showHeader": True},
            }
        ],
    }

    # Grafana will read this JSON file through its dashboard provider.
    DASHBOARD_FILE.write_text(
        json.dumps(dashboard, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Created {DASHBOARD_FILE.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
