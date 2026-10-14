-- World fossil CO2 by source, long format for charting.
UNPIVOT (
    SELECT year, coal_co2_mt AS coal, oil_co2_mt AS oil, gas_co2_mt AS gas,
           cement_co2_mt AS cement, flaring_co2_mt AS flaring, other_co2_mt AS other
    FROM core.fct_emissions
    WHERE entity = 'World' AND year >= 1900
)
ON coal, oil, gas, cement, flaring, other
INTO NAME fuel VALUE co2_mt
