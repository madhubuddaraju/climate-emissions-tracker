-- Grain: series x month. anomaly_c is relative to the 1850-1900 pre-industrial mean.
SELECT
    series,
    month::DATE           AS month,
    year(month)           AS year,
    month(month)          AS month_of_year,
    anomaly_raw_c,
    anomaly_c
FROM staging.stg_temperature
