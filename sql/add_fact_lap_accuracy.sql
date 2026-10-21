-- Add the FastF1 timing-quality flag to an existing warehouse fact table.
-- Existing rows remain NULL until reloaded from staging.
ALTER TABLE warehouse.fact_lap
    ADD COLUMN IF NOT EXISTS is_accurate BOOLEAN;
