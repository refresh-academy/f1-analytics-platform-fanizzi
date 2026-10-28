-- Create a dedicated role for Grafana without enabling login yet.
-- We will set its password interactively before allowing connections.
CREATE ROLE grafana_reader NOLOGIN;

-- Allow the role to connect to the analytics database and access the warehouse schema.
GRANT CONNECT ON DATABASE f1_analytics TO grafana_reader;
GRANT USAGE ON SCHEMA warehouse TO grafana_reader;

-- Allow reading the existing warehouse tables, without granting write permissions.
GRANT SELECT ON ALL TABLES IN SCHEMA warehouse TO grafana_reader;
