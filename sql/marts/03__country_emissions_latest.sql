-- Country scorecard for the latest year with global coverage.
WITH latest AS (
    SELECT max(year) AS y FROM core.fct_emissions WHERE entity = 'World' AND co2_mt IS NOT NULL
),
base AS (
    SELECT f.entity, f.year, f.co2_mt, f.co2_t_per_capita, f.share_global_co2_pct, f.cumulative_co2_mt,
           f.share_global_cumulative_co2_pct, f.consumption_co2_mt, f.population,
           f.coal_co2_mt, f.oil_co2_mt, f.gas_co2_mt
    FROM core.fct_emissions f, latest
    WHERE f.entity_type = 'country' AND f.year = latest.y AND f.co2_mt IS NOT NULL
),
hist AS (
    SELECT entity,
           any_value(co2_mt) FILTER (WHERE year = 1990) AS co2_1990_mt,
           any_value(co2_mt) FILTER (WHERE year = 2005) AS co2_2005_mt,
           any_value(co2_mt) FILTER (WHERE year = 2015) AS co2_2015_mt,
           -- consumption-based estimates lag territorial data by a couple of years
           arg_max(consumption_co2_mt / nullif(co2_mt, 0), year)
               FILTER (WHERE consumption_co2_mt IS NOT NULL AND co2_mt > 0) AS consumption_ratio,
           max(year) FILTER (WHERE consumption_co2_mt IS NOT NULL)        AS consumption_year
    FROM core.fct_emissions
    WHERE entity_type = 'country'
    GROUP BY entity
)
SELECT
    b.entity,
    d.iso_code,
    b.year,
    round(b.co2_mt, 1)                                         AS co2_mt,
    round(b.co2_t_per_capita, 2)                               AS co2_t_per_capita,
    round(b.share_global_co2_pct, 2)                           AS share_global_pct,
    round(b.share_global_cumulative_co2_pct, 2)                AS share_cumulative_pct,
    round(b.co2_mt / nullif(h.co2_1990_mt, 0) - 1, 4)          AS change_since_1990,
    round(b.co2_mt / nullif(h.co2_2005_mt, 0) - 1, 4)          AS change_since_2005,
    round(b.co2_mt / nullif(h.co2_2015_mt, 0) - 1, 4)          AS change_since_paris_2015,
    round(h.consumption_ratio - 1, 4)                          AS consumption_vs_territorial,
    h.consumption_year,
    round(b.coal_co2_mt / nullif(b.co2_mt, 0), 4)              AS coal_share,
    b.population,
    rank() OVER (ORDER BY b.co2_mt DESC)                       AS rank_total,
    rank() OVER (ORDER BY b.co2_t_per_capita DESC NULLS LAST)  AS rank_per_capita
FROM base b
JOIN hist h USING (entity)
JOIN core.dim_entity d ON d.entity = b.entity
ORDER BY co2_mt DESC
