-- Add the FastF1 timing-quality flag to an existing staging table.
-- Existing rows remain NULL until they are reloaded from processed Parquet.
ALTER TABLE staging.laps
    ADD COLUMN IF NOT EXISTS is_accurate BOOLEAN;
