-- Cross-check two USVIBER tables against each other. The occupancy rate (table H) should
-- equal room nights occupied (RN) / room nights available (RA). When the two disagree
-- by more than 3 points, one of the published numbers is likely a typo.
select
    island, period_date,
    hotel_occupancy_pct                                           as published_rate_pct,
    round(100.0 * room_nights_occupied_k / nullif(room_nights_available_k, 0), 1) as computed_rate_pct,
    round(hotel_occupancy_pct - 100.0 * room_nights_occupied_k / nullif(room_nights_available_k, 0), 1) as gap_pts,
    abs(hotel_occupancy_pct - 100.0 * room_nights_occupied_k / nullif(room_nights_available_k, 0)) > 3 as flagged
from {{ ref('mart_island_monthly') }}
where hotel_occupancy_pct is not null
  and room_nights_occupied_k is not null
  and room_nights_available_k is not null
