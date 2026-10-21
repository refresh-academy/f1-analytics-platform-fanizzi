-- Run after reloading existing laps with their FastF1 accuracy values.
-- Reject future staging rows that omit the quality flag.
ALTER TABLE staging.laps
    ALTER COLUMN is_accurate SET NOT NULL;
