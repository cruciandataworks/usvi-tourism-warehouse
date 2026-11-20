-- One row per island per month with every measure side by side (a "wide" table).
-- This is the shape analysts and dashboards like best.
with f as (select * from {{ ref('fct_tourism_monthly') }}),
wide as (
    select
        island, period_date, period_year, period_month,
        max(value) filter (where series_code = 'A')  as air_arrivals,
        max(value) filter (where series_code = 'CP') as cruise_passengers,
        max(value) filter (where series_code = 'CS') as cruise_ship_calls,
        max(value) filter (where series_code = 'H')  as hotel_occupancy_pct,
        max(value) filter (where series_code = 'RA') as room_nights_available_k,
        max(value) filter (where series_code = 'RN') as room_nights_occupied_k
    from f
    group by all
),
-- Rooms exist on one island only, so the territory's room nights are the sum of the
-- islands. USVIBER's printed territory column for rooms available often disagrees with
-- its own island columns (see mart_island_consistency), so we compute it instead.
rooms as (
    select period_date,
           sum(room_nights_available_k) as ra_sum, count(room_nights_available_k) as ra_n,
           sum(room_nights_occupied_k)  as rn_sum, count(room_nights_occupied_k)  as rn_n
    from wide where island <> 'USVI' group by 1
),
wide_fixed as (
    select w.* replace (
        case when w.island = 'USVI' and r.ra_n = 2 then round(r.ra_sum, 1) else w.room_nights_available_k end as room_nights_available_k,
        case when w.island = 'USVI' and r.rn_n = 2 then round(r.rn_sum, 1) else w.room_nights_occupied_k end as room_nights_occupied_k
    )
    from wide w left join rooms r using (period_date)
)
select
    w.*,
    -- Only add the two when both are published, so a gap never looks like a drop.
    case when w.air_arrivals is not null and w.cruise_passengers is not null
         then w.air_arrivals + w.cruise_passengers end                 as total_visitors,
    round(w.cruise_passengers / nullif(w.cruise_ship_calls, 0), 0)     as passengers_per_ship_call,
    -- Same month last year, for year-over-year change
    round(100.0 * (w.air_arrivals / nullif(ly.air_arrivals, 0) - 1), 1)           as air_yoy_pct,
    round(100.0 * (w.cruise_passengers / nullif(ly.cruise_passengers, 0) - 1), 1) as cruise_yoy_pct,
    round(w.hotel_occupancy_pct - ly.hotel_occupancy_pct, 1)                    as occupancy_yoy_pts
from wide_fixed w
left join wide_fixed ly
    on ly.island = w.island
   and ly.period_date = w.period_date - interval 1 year
