-- A PDF we could not read is only acceptable if it is listed, with a reason, in
-- seeds/known_unreadable_files.csv. A new unreadable file fails the build so a person
-- looks at it before the dashboard silently loses a month.
select file_name, extract_note
from {{ ref('mart_report_files') }}
where extract_status = 'failed' and known_issue is null
