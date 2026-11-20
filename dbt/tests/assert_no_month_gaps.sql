-- Between each series' first and latest month, every month must have a territory value.
-- Known gap: cruise passengers October 2017 (Hurricanes Irma and Maria closed the ports).
with f as (select * from {{ ref('fct_tourism_monthly') }} where island = 'USVI'),
bounds as (select series_code, min(period_date) lo, max(period_date) hi from f group by 1),
spine as (
    select series_code, unnest(generate_series(lo, hi, interval 1 month))::date as period_date
    from bounds
)
select s.* from spine s
left join f using (series_code, period_date)
where f.value is null
  and not (s.series_code = 'CP' and s.period_date = date '2017-10-01')
