-- Severity is "warn": USVIBER revises past months, so a later report can legitimately
-- move these totals. A warning tells us to re-check the homepage; it should not block
-- the monthly refresh.
{{ config(severity='warn') }}
-- Our warehouse must reproduce the headline numbers USVIBER shows on usviber.org
-- (checked 2026-11-19): air arrivals 744,449 and cruise arrivals 1,493,974, both
-- January-August 2026 year to date. Any row returned = a failed test.
-- Allowed drift: 2 visitors. USVIBER's own eight monthly air figures add up to 744,448,
-- one less than its printed total - a rounding difference in their estimates.
with ytd as (
    select series_code, sum(value) as total
    from {{ ref('fct_tourism_monthly') }}
    where island = 'USVI' and period_date between date '2026-01-01' and date '2026-08-01'
      and series_code in ('A', 'CP')
    group by 1
),
expected as (
    select * from (values ('A', 744449), ('CP', 1493974)) as t(series_code, expected_total)
)
select e.series_code, e.expected_total, y.total
from expected e left join ytd y using (series_code)
where y.total is null or abs(y.total - e.expected_total) > 2
