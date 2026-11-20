-- The newest report of each count series (air arrivals, cruise passengers, ship calls)
-- must add up: its January-to-date months for the territory total must equal its
-- printed YEAR TO DATE line. This proves step 3 read the right numbers into the right
-- columns. Older reports, single islands and room nights are reported in
-- mart_reconciliation instead, because a few of USVIBER's printed totals carry typos.
select * from {{ ref('mart_reconciliation') }}
where is_latest_report and island = 'USVI' and series_code in ('A', 'CP', 'CS')
  and status not in ('reconciled', 'reconciled (rounding)')
