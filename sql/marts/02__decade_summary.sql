-- Decade-level view of warming, CO2 accumulation and emissions (complete years only).
WITH a AS (
    SELECT *, (year // 10) * 10 AS decade FROM marts.annual_climate WHERE temp_year_complete
),
d AS (
    SELECT
        decade,
        count(*)                                  AS years,
        avg(temp_anomaly_c)                       AS avg_temp_anomaly_c,
        max(temp_anomaly_c)                       AS max_temp_anomaly_c,
        avg(co2_ppm) FILTER (WHERE co2_year_complete) AS avg_co2_ppm,
        sum(world_co2_mt)                         AS decade_co2_mt
    FROM a
    GROUP BY decade
)
SELECT
    decade,
    years,
    round(avg_temp_anomaly_c, 3)                                              AS avg_temp_anomaly_c,
    round(max_temp_anomaly_c, 3)                                              AS max_temp_anomaly_c,
    round(avg_temp_anomaly_c - lag(avg_temp_anomaly_c) OVER (ORDER BY decade), 3) AS warming_vs_prev_decade_c,
    round(avg_co2_ppm, 1)                                                     AS avg_co2_ppm,
    round(decade_co2_mt / 1000, 1)                                            AS decade_co2_gt
FROM d
ORDER BY decade
