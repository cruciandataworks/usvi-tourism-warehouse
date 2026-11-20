-- Every report file with its extraction outcome, and the documented reason for any
-- file we could not use.
select f.*, k.reason as known_issue
from {{ ref('stg_report_files') }} f
left join {{ ref('known_unreadable_files') }} k using (file_name)
