-- Run after the metrics table and the existing Grafana telemetry role exist.
-- Allow the dashboard to read metrics through its current data source.
GRANT SELECT ON TABLE public.telemetry_speed_5s TO grafana_telemetry_reader;
