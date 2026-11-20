-- Data quality check, file by file: do the monthly numbers in a report add up to the
-- YEAR TO DATE total printed on that same report? Run for every additive series
-- (arrivals, ship calls, room nights). Hotel occupancy is a rate, so it is skipped.
with o as (select * from {{ ref('stg_observations') }}),
ytd as (select * from o where row_kind = 'ytd'),
summed as (
    select y.media_id, y.series_code, y.island, y.period_year, y.period_month as through_month,
           y.value as printed_ytd,
           sum(m.value) as summed_months,
           count(m.value) as months_found
    from ytd y
    join {{ ref('series') }} s on s.series_code = y.series_code and s.additive
    left join o m
      on m.media_id = y.media_id and m.row_kind = 'month' and m.island = y.island
     and m.period_year = y.period_year and m.period_month <= y.period_month
    group by all
)
select
    s.*,
    f.file_name,
    f.uploaded_at,
    f.source_url,
    round(summed_months - printed_ytd, 1)                                   as difference,
    round(100.0 * abs(summed_months - printed_ytd) / nullif(printed_ytd, 0), 3) as difference_pct,
    case
        when abs(summed_months - printed_ytd) <= greatest(0.1, printed_ytd * {{ var('reconcile_tolerance_pct') }} / 100)
            then 'reconciled'
        -- room nights are printed in thousands to one decimal, so rounding adds up
        when s.series_code in ('RA', 'RN') and abs(summed_months - printed_ytd) <= 0.1 * through_month
            then 'reconciled (rounding)'
        -- a month printed as "-" (e.g. October 2017, ports closed after Hurricane Maria)
        when months_found < through_month then 'months missing'
        else 'mismatch'
    end as status,
    row_number() over (partition by s.series_code, s.island, s.period_year order by f.uploaded_at desc, s.media_id desc) = 1
        as is_latest_report
from summed s
join {{ ref('stg_report_files') }} f using (media_id)
