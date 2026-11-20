-- One row per report PDF: where it came from, when it was uploaded, and whether step 3 could read it.
select
    cast(m.media_id as integer)              as media_id,
    m.file_name,
    cast(m.uploaded_at as timestamp)         as uploaded_at,
    m.series_code,
    cast(m.name_year as integer)             as name_year,
    cast(m.name_month as integer)            as name_month,
    m.url                                    as source_url,
    d.sha256,
    cast(d.bytes as integer)                 as bytes,
    l.status                                 as extract_status,
    cast(l."values" as integer)              as values_read,
    nullif(l.note, '')                       as extract_note
from {{ source('raw', 'report_manifest') }} m
left join {{ source('raw', 'report_downloads') }} d using (media_id)
left join {{ source('raw', 'extract_log') }} l using (media_id)
