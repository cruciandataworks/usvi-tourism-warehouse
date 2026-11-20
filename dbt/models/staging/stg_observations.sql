-- One row per number in a report, typed, with the file's upload time attached so we
-- can tell which report is newest for any given month.
select
    cast(o.media_id as integer)              as media_id,
    o.series_code,
    o.row_kind,                              -- month | ytd | annual
    cast(o.column_year as integer)           as period_year,
    cast(o.period_month as integer)          as period_month,
    make_date(cast(o.column_year as integer), cast(o.period_month as integer), 1) as period_date,
    o.island,
    cast(o.value as double)                  as value,
    f.uploaded_at,
    f.file_name,
    f.source_url
from {{ source('raw', 'observations') }} o
join {{ ref('stg_report_files') }} f on f.media_id = cast(o.media_id as integer)
