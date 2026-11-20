-- Do the islands add up to the territory? A source-data check, month by month.
--   Air arrivals, room nights: every visitor or room is on one island, so
--     St. Thomas/St. John + St. Croix should equal the U.S.V.I. total.
--   Cruise passengers and ship calls: one ship can call at both islands, and USVIBER
--     counts it once in the total, so the total may be smaller - but never larger.
with f as (select * from {{ ref('fct_tourism_monthly') }} where series_code <> 'H'),
j as (
    select t.series_code, t.period_date, t.value as published_total,
           a.value as stt_stj, b.value as stx, a.value + b.value as islands_sum,
           t.source_file, t.source_url
    from f t
    join f a on a.series_code = t.series_code and a.period_date = t.period_date and a.island = 'STT_STJ'
    join f b on b.series_code = t.series_code and b.period_date = t.period_date and b.island = 'STX'
    where t.island = 'USVI'
)
select
    *,
    round(published_total - islands_sum, 1) as gap,
    case
        when series_code = 'A' then abs(published_total - islands_sum) > 2           -- ±2 = rounding
        when series_code in ('RA', 'RN') then abs(published_total - islands_sum) > 0.3
        else published_total > islands_sum + 1
    end as flagged
from j
