-- Months whose number changed after first publication (USVIBER revises as late
-- surveys come in). Useful to show a client why "the number moved".
select
    series_code, series, island, period_date,
    first_published_value, value as latest_value,
    round(value - first_published_value, 1) as change,
    round(100.0 * (value / nullif(first_published_value, 0) - 1), 2) as change_pct,
    first_published_at, source_uploaded_at as latest_published_at, times_published
from {{ ref('fct_tourism_monthly') }}
where was_revised
