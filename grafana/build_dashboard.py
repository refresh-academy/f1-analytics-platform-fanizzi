"""Build the Monza 2024 Grafana dashboard from the reviewed SQL query."""

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / "sql" / "driver_lap_summary.sql"
COMPOUND_SQL_FILE = ROOT / "sql" / "grafana_driver_compound_laps.sql"
STINT_SQL_FILE = ROOT / "sql" / "driver_stint_summary.sql"
LAP_TIME_SQL_FILE = ROOT / "sql" / "grafana_lap_time_comparison.sql"
RESULT_SQL_FILE = ROOT / "sql" / "grafana_hamilton_leclerc_result.sql"
SECTOR_SQL_FILE = ROOT / "sql" / "grafana_sector_medians.sql"
DRIVER_OPTIONS_SQL_FILE = ROOT / "sql" / "grafana_sector_driver_options.sql"
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

    # Read the compound totals for the stacked bar panel.
    compound_query = COMPOUND_SQL_FILE.read_text(encoding="utf-8")

    stint_query = STINT_SQL_FILE.read_text(encoding="utf-8")

    lap_time_query = LAP_TIME_SQL_FILE.read_text(encoding="utf-8")

    result_query = RESULT_SQL_FILE.read_text(encoding="utf-8")

    # Keep the sector calculation in its reviewed SQL file.
    sector_query = SECTOR_SQL_FILE.read_text(encoding="utf-8")

    # Both driver selectors use the same list of race participants.
    driver_options_query = DRIVER_OPTIONS_SQL_FILE.read_text(encoding="utf-8")

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
        # This fixed 2024 race snapshot does not use a time filter.
        "timepicker": {"hidden": True},
        # Two single-choice menus keep the sector chart to two drivers.
        # __text shows the name and sample size; __value is the race number.
        "templating": {
            "list": [
                {
                    "name": name,
                    "label": label,
                    "type": "query",
                    "datasource": datasource,
                    "definition": driver_options_query,
                    "query": driver_options_query,
                    "current": {"text": selected_text, "value": number},
                    "options": [],
                    "refresh": 1,
                    "hide": 0,
                    "multi": False,
                    "includeAll": False,
                    "sort": 0,
                }
                for name, label, selected_text, number in (
                    (
                        "sector_driver_a", "Sector chart only: Driver A",
                        "Charles Leclerc (50 usable laps)", "16",
                    ),
                    (
                        "sector_driver_b", "Sector chart only: Driver B",
                        "Oscar Piastri (48 usable laps)", "81",
                    ),
                )
            ]
        },
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
                "gridPos": {"h": 12, "w": 24, "x": 0, "y": 18},
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
            },
            {
                "id": 2,
                "title": "Recorded race laps by tyre compound (totals)",
                "description": (
                    "The horizontal scale counts recorded laps, not race lap "
                    "numbers. Each colour sums all stints on that compound; "
                    "segments do not show stint order. Hover for exact counts."
                ),
                "type": "barchart",
                # Use the familiar F1 colours for the three tyre compounds.
                "fieldConfig": {
                    "defaults": {
                        "custom": {"axisLabel": "Recorded laps (stacked count)"}
                    },
                    "overrides": [
                        {
                            "matcher": {"id": "byName", "options": compound},
                            "properties": [
                                {
                                    "id": "color",
                                    "value": {
                                        "mode": "fixed",
                                        "fixedColor": color,
                                    },
                                }
                            ],
                        }
                        for compound, color in (
                            ("HARD", "#F2F2F2"),
                            ("MEDIUM", "#FFD500"),
                            ("SOFT", "#E10600"),
                        )
                    ],
                },
                "gridPos": {"h": 18, "w": 24, "x": 0, "y": 0},
                "datasource": datasource,
                "targets": [
                    {
                        "refId": "A",
                        "datasource": datasource,
                        "editorMode": "code",
                        "rawQuery": True,
                        "rawSql": compound_query,
                        "format": "table",
                    }
                ],
                "options": {
                    "xField": "driver",
                    "orientation": "horizontal",
                    "stacking": "normal",
                    "showValue": "never",
                    "legend": {
                        "showLegend": True,
                        "displayMode": "list",
                        "placement": "bottom",
                    },
                },
            },
            {
                "id": 3,
                "title": "Stint sequence by driver (race lap ranges)",
                "description": (
                    "One row per recorded stint. First and last lap are "
                    "inclusive race lap numbers; repeated compounds are "
                    "separate stints."
                ),
                "type": "table",
                "gridPos": {"h": 16, "w": 24, "x": 0, "y": 30},
                "datasource": datasource,
                "targets": [
                    {
                        "refId": "A",
                        "datasource": datasource,
                        "editorMode": "code",
                        "rawQuery": True,
                        "rawSql": stint_query,
                        "format": "table",
                    }
                ],
                "options": {"showHeader": True},
            },
            {
                "id": 4,
                "title": "Recorded lap times: Leclerc vs Piastri",
                "description": (
                    "One point per recorded lap passing FastF1's basic "
                    "IsAccurate check. Missing points are not proof of "
                    "deleted or incorrect times. Race-control deletion "
                    "data is unavailable; these are not official results."
                ),
                "type": "xychart",
                "gridPos": {"h": 16, "w": 24, "x": 0, "y": 46},
                "datasource": datasource,
                "fieldConfig": {
                    "defaults": {
                        "custom": {
                            "show": "points",
                            "pointSize": {"fixed": 5},
                            "axisLabel": "Lap time (s)",
                        }
                    },
                    # The x field counts race laps; the y fields show seconds.
                    "overrides": [
                        {
                            "matcher": {"id": "byName", "options": "lap_number"},
                            "properties": [
                                {
                                    "id": "custom.axisLabel",
                                    "value": "Race lap number",
                                }
                            ],
                        }
                    ],
                },
                "targets": [
                    {
                        "refId": "A",
                        "datasource": datasource,
                        "editorMode": "code",
                        "rawQuery": True,
                        "rawSql": lap_time_query,
                        "format": "table",
                    }
                ],
                "options": {
                    "mapping": "auto",
                    "series": [{}],
                    "legend": {
                        "showLegend": True,
                        "displayMode": "list",
                        "placement": "bottom",
                    },
                },
            },
            {
                "id": 5,
                "title": "Final position: Leclerc (winner) vs Hamilton",
                "description": (
                    "Classified race positions from the preserved FastF1 "
                    "results, not from lap times. Position 1 wins; a lower "
                    "number is better, even when its bar is shorter."
                ),
                "type": "barchart",
                "gridPos": {"h": 9, "w": 24, "x": 0, "y": 62},
                "datasource": datasource,
                "fieldConfig": {
                    "defaults": {
                        "decimals": 0,
                        "custom": {
                            "axisLabel": "Classified position (1 = winner)"
                        },
                    },
                    "overrides": [],
                },
                "targets": [
                    {
                        "refId": "A",
                        "datasource": datasource,
                        "editorMode": "code",
                        "rawQuery": True,
                        "rawSql": result_query,
                        "format": "table",
                    }
                ],
                "options": {
                    "xField": "driver",
                    "orientation": "horizontal",
                    "stacking": "none",
                    "showValue": "always",
                    "legend": {"showLegend": False},
                },
            },
            {
                "id": 6,
                "title": (
                    "Median sector times: ${sector_driver_a:text} vs "
                    "${sector_driver_b:text}"
                ),
                "description": (
                    "The two driver menus above affect only this sector "
                    "chart; each shows the number of usable laps. Medians "
                    "use only FastF1 "
                    "IsAccurate laps with all three sector times. Values "
                    "are seconds; lower means a shorter median sector "
                    "time. Tyres and traffic are not controlled for, "
                    "and these are not official rankings."
                ),
                "type": "barchart",
                "gridPos": {"h": 11, "w": 24, "x": 0, "y": 71},
                "datasource": datasource,
                "fieldConfig": {
                    "defaults": {
                        "decimals": 3,
                        "custom": {"axisLabel": "Median sector time (s)"},
                    },
                    # Match the SQL fields, then show the selected names
                    # in the legend instead of the generic A/B labels.
                    "overrides": [
                        {
                            "matcher": {
                                "id": "byName",
                                "options": "Driver A (s)",
                            },
                            "properties": [
                                {
                                    "id": "displayName",
                                    "value": "${sector_driver_a:text}",
                                }
                            ],
                        },
                        {
                            "matcher": {
                                "id": "byName",
                                "options": "Driver B (s)",
                            },
                            "properties": [
                                {
                                    "id": "displayName",
                                    "value": "${sector_driver_b:text}",
                                }
                            ],
                        },
                    ],
                },
                "targets": [
                    {
                        "refId": "A",
                        "datasource": datasource,
                        "editorMode": "code",
                        "rawQuery": True,
                        "rawSql": sector_query,
                        "format": "table",
                    }
                ],
                "options": {
                    "xField": "sector",
                    "orientation": "horizontal",
                    "stacking": "none",
                    "showValue": "always",
                    "legend": {
                        "showLegend": True,
                        "displayMode": "list",
                        "placement": "bottom",
                    },
                },
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
