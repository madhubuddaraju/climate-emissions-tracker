-- Continents and income groups over time (they overlap each other, so never sum across groups).
SELECT
    entity                                  AS region,
    CASE WHEN entity LIKE '%income%' THEN 'income group'
         WHEN entity IN ('International aviation', 'International shipping') THEN 'transport'
         WHEN entity = 'World' THEN 'world'
         ELSE 'continent' END               AS grouping,
    year,
    round(co2_mt, 1)                        AS co2_mt,
    round(co2_mt * 1e6 / population, 2)     AS co2_t_per_capita
FROM core.fct_emissions
WHERE entity_type = 'region' AND year >= 1950 AND co2_mt IS NOT NULL
ORDER BY region, year
