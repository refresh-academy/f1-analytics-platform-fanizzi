-- Create the Grafana telemetry reader before configuring its password.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'grafana_telemetry_reader'
    ) THEN
        CREATE ROLE grafana_telemetry_reader NOLOGIN;
    END IF;
END;
$$;

-- Allow connections and access to the schema containing telemetry.
GRANT CONNECT ON DATABASE f1_telemetry TO grafana_telemetry_reader;
GRANT USAGE ON SCHEMA public TO grafana_telemetry_reader;

-- Grant read access to the telemetry table.
GRANT SELECT ON TABLE public.telemetry_events TO grafana_telemetry_reader;
