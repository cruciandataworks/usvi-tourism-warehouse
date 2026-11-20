-- Calendar-year totals per island. Partial years are labelled with how many months
-- they include, so 2026 (January to August) is never compared to a full year by mistake.
with m as (select * from {{ ref('mart_island_monthly') }})
select
    island,
    period_year,
    count(air_arrivals)                    as air_months,
    count(cruise_passengers)               as cruise_months,
    sum(air_arrivals)                      as air_arrivals,
    sum(cruise_passengers)                 as cruise_passengers,
    sum(cruise_ship_calls)                 as cruise_ship_calls,
    -- Annual occupancy is occupied / available, not an average of 12 monthly rates
    round(100.0 * sum(room_nights_occupied_k) filter (where room_nights_available_k is not null)
          / nullif(sum(room_nights_available_k) filter (where room_nights_occupied_k is not null), 0), 1)
                                           as hotel_occupancy_pct,
    count(hotel_occupancy_pct)             as hotel_months
from m
group by all
