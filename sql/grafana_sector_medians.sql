-- Compare median recorded sector times for two selected Monza 2024 drivers.
-- Keep only laps passing FastF1's basic IsAccurate check and containing
-- all three sector times. The same eligible laps feed S1, S2, and S3.
-- Medians describe this sample; they do not control for tyres or traffic.
-- A CTE names the set of laps admitted to every sector calculation.
-- Keeping this filter in one place avoids using different laps for S1,
-- S2, and S3 for the same driver.
WITH eligible_laps AS (
    SELECT
        lap.driver_number,
        lap.sector1_seconds,
        lap.sector2_seconds,
        lap.sector3_seconds
    FROM warehouse.fact_lap AS lap
    -- session_id links each lap to its season, event, and session.
    JOIN warehouse.dim_session AS session
        ON session.session_id = lap.session_id
    WHERE session.season = 2024
      AND session.event_name = 'Italian Grand Prix'
      AND session.session_name = 'Race'
      -- Grafana substitutes the two selected race numbers here.
      AND lap.driver_number IN (
          ${sector_driver_a:sqlstring}, ${sector_driver_b:sqlstring}
      )
      -- IsAccurate is FastF1's basic timing check, not proof that a
      -- lap is official or that other laps are incorrect.
      AND lap.is_accurate
      -- Require all three times on each admitted lap. In this source,
      -- sector 1 is missing for every driver's first lap.
      AND lap.sector1_seconds IS NOT NULL
      AND lap.sector2_seconds IS NOT NULL
      AND lap.sector3_seconds IS NOT NULL
)
-- percentile_cont(0.5) computes the median; for an even number of
-- laps it interpolates between the two central sector times.
-- FILTER gives each driver a separate median. ROUND changes only
-- the displayed result to three decimal places (seconds).
SELECT
    sector.name AS sector,
    ROUND(
        (percentile_cont(0.5) WITHIN GROUP (ORDER BY sector.seconds)
            FILTER (WHERE lap.driver_number = ${sector_driver_a:sqlstring}))::numeric,
        3
    ) AS "Driver A (s)",
    ROUND(
        (percentile_cont(0.5) WITHIN GROUP (ORDER BY sector.seconds)
            FILTER (WHERE lap.driver_number = ${sector_driver_b:sqlstring}))::numeric,
        3
    ) AS "Driver B (s)"
FROM eligible_laps AS lap
-- LATERAL lets VALUES read the current lap's sector columns.
-- It turns each eligible lap into three labelled rows: S1, S2, S3.
CROSS JOIN LATERAL (
    VALUES
        ('S1', 1, lap.sector1_seconds),
        ('S2', 2, lap.sector2_seconds),
        ('S3', 3, lap.sector3_seconds)
) AS sector(name, display_order, seconds)
-- Group equal sector labels across laps before calculating medians;
-- retain display_order so the output follows the track's sector order.
GROUP BY sector.name, sector.display_order
ORDER BY sector.display_order;
