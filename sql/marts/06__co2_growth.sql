-- Annual growth of atmospheric CO2, measured December-to-December on the seasonally adjusted series.
WITH dec AS (
    SELECT year, co2_deseasonalized_ppm AS dec_ppm
    FROM core.fct_co2_monthly
    WHERE month_of_year = 12 AND co2_deseasonalized_ppm IS NOT NULL
),
g AS (
    SELECT year, dec_ppm, dec_ppm - lag(dec_ppm) OVER (ORDER BY year) AS growth_ppm FROM dec
)
SELECT
    year,
    round(dec_ppm, 2)                                                   AS dec_deseasonalized_ppm,
    round(growth_ppm, 2)                                                AS growth_ppm,
    round(avg(growth_ppm) OVER (ORDER BY year ROWS 9 PRECEDING), 2)     AS growth_ppm_10yr_avg
FROM g
ORDER BY year
