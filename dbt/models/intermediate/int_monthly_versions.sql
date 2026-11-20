-- Every report reprints last year's months, and USVIBER revises them. So one month can
-- appear in a dozen files. This model ranks those copies: version 1 = first published,
-- and is_latest marks the newest upload, which is the number we report.
select
    series_code,
    island,
    period_year,
    period_month,
    period_date,
    value,
    media_id,
    file_name,
    source_url,
    uploaded_at,
    row_number() over w_first                         as version_number,
    row_number() over w_latest = 1                    as is_latest,
    count(*) over (partition by series_code, island, period_date) as copies
from {{ ref('stg_observations') }}
where row_kind = 'month'
window
    w_first  as (partition by series_code, island, period_date order by uploaded_at, media_id),
    w_latest as (partition by series_code, island, period_date order by uploaded_at desc, media_id desc)
