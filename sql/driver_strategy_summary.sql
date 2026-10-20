-- Summarize the recorded stint sequence for each Monza 2024 race driver.
-- The result has one row per driver; the source fact table has one row per stint.
SELECT
    driver.full_name,
    participation.team_name,
    participation.driver_number,

    -- After grouping by driver, COUNT(*) counts that driver's stint rows.
    COUNT(*) AS stint_count,

    -- STRING_AGG joins text values into one string.
    -- The separator is " -> ", and ORDER BY preserves stint order.
    -- Repeated values remain visible: HARD -> HARD means two distinct stints.
    STRING_AGG(stint.compound, ' -> ' ORDER BY stint.stint_number)
        AS compound_sequence,

    -- SUM adds the recorded lap counts from all of this driver's stints.
    -- This is a count of available lap records, not tyre age.
    SUM(stint.recorded_laps) AS recorded_laps

-- Start with the stint fact table: one stored row per driver and stint.
FROM warehouse.fact_stint AS stint

-- session_id connects each stint to its season, event, and session.
JOIN warehouse.dim_session AS session
    ON session.session_id = stint.session_id

-- A driver number and team belong to the driver's participation
-- in this session, rather than to the driver's permanent identity.
JOIN warehouse.session_driver AS participation
    ON participation.session_id = stint.session_id
   AND participation.driver_number = stint.driver_number

-- driver_id connects that participation to the driver's name.
JOIN warehouse.dim_driver AS driver
    ON driver.driver_id = participation.driver_id

-- Restrict the analysis to the race currently covered by this project.
WHERE session.season = 2024
  AND session.event_name = 'Italian Grand Prix'
  AND session.session_name = 'Race'

-- GROUP BY collects all stint rows belonging to the same driver.
-- Include the driver identifier so equal names would not merge drivers.
GROUP BY
    driver.driver_id,
    driver.full_name,
    participation.team_name,
    participation.driver_number

-- Show drivers with more stints first; use the name to break ties.
ORDER BY stint_count DESC, driver.full_name;
