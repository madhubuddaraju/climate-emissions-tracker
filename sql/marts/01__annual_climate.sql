-- One row per year: temperature, atmospheric CO2 and global emissions side by side.
WITH temp AS (
    SELECT year,
           avg(anomaly_c) FILTER (WHERE series = 'GCAG')    AS temp_anomaly_c,
           avg(anomaly_c) FILTER (WHERE series = 'GISTEMP') AS temp_anomaly_gistemp_c,
           count(*)       FILTER (WHERE series = 'GCAG')    AS temp_months
    FROM core.fct_temperature_monthly
    GROUP BY year
),
co2 AS (
    SELECT year, avg(co2_ppm) AS co2_ppm, count(*) AS co2_months
    FROM core.fct_co2_monthly
    GROUP BY year
),
emis AS (
    SELECT year, co2_mt, total_ghg_mt, cumulative_co2_mt, population
    FROM core.fct_emissions
    WHERE entity = 'World'
)
SELECT
    t.year,
    round(t.temp_anomaly_c, 3)                                                AS temp_anomaly_c,
    round(t.temp_anomaly_gistemp_c, 3)                                        AS temp_anomaly_gistemp_c,
    round(avg(t.temp_anomaly_c) OVER (ORDER BY t.year ROWS 9 PRECEDING), 3)   AS temp_anomaly_10yr_c,
    t.temp_months = 12                                                        AS temp_year_complete,
    round(c.co2_ppm, 2)                                                       AS co2_ppm,
    coalesce(c.co2_months = 12, FALSE)                                        AS co2_year_complete,
    round(e.co2_mt, 1)                                                        AS world_co2_mt,
    round(e.total_ghg_mt, 1)                                                  AS world_ghg_mt,
    round(e.cumulative_co2_mt, 0)                                             AS world_cumulative_co2_mt,
    round(e.co2_mt * 1e6 / e.population, 3)                                   AS world_co2_t_per_capita,
    round(e.co2_mt / lag(e.co2_mt) OVER (ORDER BY t.year) - 1, 4)             AS world_co2_yoy
FROM temp t
LEFT JOIN co2  c USING (year)
LEFT JOIN emis e USING (year)
ORDER BY t.year
