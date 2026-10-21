-- Run after loading accuracy values into all existing lap facts.
-- Every future warehouse lap must carry the FastF1 quality flag.
ALTER TABLE warehouse.fact_lap
    ALTER COLUMN is_accurate SET NOT NULL;
