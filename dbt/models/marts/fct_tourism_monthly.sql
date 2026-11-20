-- The warehouse's core table: one number per series, island and month, taken from the
-- most recent report that printed it. We keep the first published value as well, so a
-- revision is visible instead of silently overwritten.
with v as (select * from {{ ref('int_monthly_versions') }}),
first_pub as (
    select series_code, island, period_date, value as first_published_value,
           uploaded_at as first_published_at
    from v where version_number = 1
)
select
    {{ dbt_utils_surrogate_key(['v.series_code', 'v.island', 'v.period_date']) }} as tourism_monthly_id,
    v.series_code,
    s.series,
    s.unit,
    v.island,
    v.period_date,
    v.period_year,
    v.period_month,
    v.value,
    f.first_published_value,
    f.first_published_at,
    v.copies                                         as times_published,
    v.value <> f.first_published_value              as was_revised,
    v.file_name                                      as source_file,
    v.source_url,
    v.uploaded_at                                    as source_uploaded_at
from v
join first_pub f using (series_code, island, period_date)
join {{ ref('series') }} s using (series_code)
where v.is_latest
