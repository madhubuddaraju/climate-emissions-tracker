-- Has a country grown its economy while cutting CO2? Compares 2010 with the latest year that has GDP.
WITH last_gdp AS (
    SELECT max(year) AS y FROM core.fct_emissions WHERE entity_type = 'country' AND gdp IS NOT NULL
),
pairs AS (
    SELECT
        f.entity,
        any_value(f.gdp)    FILTER (WHERE f.year = 2010)  AS gdp_start,
        any_value(f.gdp)    FILTER (WHERE f.year = l.y)   AS gdp_end,
        any_value(f.co2_mt) FILTER (WHERE f.year = 2010)  AS co2_start,
        any_value(f.co2_mt) FILTER (WHERE f.year = l.y)   AS co2_end,
        any_value(l.y)                                     AS end_year
    FROM core.fct_emissions f, last_gdp l
    WHERE f.entity_type = 'country'
    GROUP BY f.entity
)
SELECT
    entity,
    2010                                          AS start_year,
    end_year,
    round(gdp_end / gdp_start - 1, 4)             AS gdp_change,
    round(co2_end / co2_start - 1, 4)             AS co2_change,
    round(co2_end, 1)                             AS co2_end_mt,
    CASE
        WHEN gdp_end > gdp_start AND co2_end < co2_start THEN 'Absolute decoupling'
        WHEN gdp_end > gdp_start AND co2_end / co2_start < gdp_end / gdp_start THEN 'Relative decoupling'
        WHEN gdp_end > gdp_start THEN 'Coupled growth'
        ELSE 'Economic decline'
    END                                           AS status
FROM pairs
WHERE gdp_start IS NOT NULL AND gdp_end IS NOT NULL AND co2_start > 10   -- skip very small emitters
ORDER BY co2_end DESC
