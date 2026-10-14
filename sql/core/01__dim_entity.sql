-- One row per country or region, with its latest population.
SELECT
    country                                         AS entity,
    any_value(iso_code)                             AS iso_code,
    any_value(entity_type)                          AS entity_type,
    min(year) FILTER (WHERE co2 IS NOT NULL)        AS first_year_with_co2,
    max(year) FILTER (WHERE co2 IS NOT NULL)        AS last_year_with_co2,
    arg_max(population, year) FILTER (WHERE population IS NOT NULL) AS latest_population
FROM staging.stg_emissions
GROUP BY country
