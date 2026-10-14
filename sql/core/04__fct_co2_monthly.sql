-- Grain: month. Mauna Loa monthly mean CO2 (ppm) and its seasonally adjusted value.
SELECT
    month::DATE                                 AS month,
    year(month)                                 AS year,
    month(month)                                AS month_of_year,
    co2_ppm,
    co2_deseasonalized_ppm,
    round(co2_ppm - co2_deseasonalized_ppm, 3)  AS seasonal_component_ppm,
    days                                        AS measurement_days
FROM staging.stg_co2_ppm
