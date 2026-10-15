-- Require every warehouse lap to have a driver in the same session.
-- Apply this after warehouse.session_driver has been populated.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'warehouse.fact_lap'::regclass
          AND conname = 'fact_lap_driver_fkey'
    ) THEN
        ALTER TABLE warehouse.fact_lap
            ADD CONSTRAINT fact_lap_driver_fkey
            FOREIGN KEY (session_id, driver_number)
            REFERENCES warehouse.session_driver (session_id, driver_number);
    END IF;
END
$$;
