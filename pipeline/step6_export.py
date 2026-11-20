"""Step 6 - Export: write small JSON files the website dashboard reads.

The dashboard is a static web page (no server, no database), so we pre-compute the
numbers it needs from the marts and save them next to it. Queries are sorted, so
identical data gives identical files and the monthly job only commits real changes.

Output: dashboard/data/*.json
"""
import json
from datetime import date, datetime
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "tourism.duckdb"
OUT = ROOT / "dashboard" / "data"

QUERIES = {
    "monthly": """
        select island, strftime(period_date, '%Y-%m') as month,
               air_arrivals as air, cruise_passengers as cruise, cruise_ship_calls as calls,
               hotel_occupancy_pct as occ, room_nights_available_k as rooms_avail,
               room_nights_occupied_k as rooms_occ, total_visitors as total,
               passengers_per_ship_call as ppc, air_yoy_pct as air_yoy,
               cruise_yoy_pct as cruise_yoy, occupancy_yoy_pts as occ_yoy
        from marts.mart_island_monthly order by island, period_date""",
    "annual": """
        select island, period_year as year, air_months, cruise_months, air_arrivals as air,
               cruise_passengers as cruise, cruise_ship_calls as calls,
               hotel_occupancy_pct as occ, hotel_months
        from marts.mart_annual order by island, period_year""",
    "revisions": """
        select series_code, island, strftime(period_date, '%Y-%m') as month,
               first_published_value as first, latest_value as latest, change_pct,
               strftime(first_published_at, '%Y-%m-%d') as first_at,
               strftime(latest_published_at, '%Y-%m-%d') as latest_at, times_published
        from marts.mart_revisions
        where island = 'USVI' and series_code in ('A', 'CP', 'CS')
        order by abs(change_pct) desc, series_code, month limit 12""",
    "occupancy_flags": """
        select island, strftime(period_date, '%Y-%m') as month, published_rate_pct as published,
               computed_rate_pct as computed, gap_pts
        from marts.mart_occupancy_check
        where flagged and period_date >= date '2024-01-01'
        order by period_date desc, island""",
    "island_flags": """
        select series_code, strftime(period_date, '%Y-%m') as month, published_total,
               stt_stj, stx, islands_sum, gap, source_file, source_url
        from marts.mart_island_consistency
        where flagged and series_code in ('A', 'CP', 'CS', 'RN')
        order by period_date desc, series_code""",
    "files": """
        select series_code, count(*) as files,
               count(*) filter (where extract_status = 'ok') as read_ok,
               count(*) filter (where extract_note is not null and extract_status = 'ok') as label_fixed,
               min(uploaded_at)::date as first_upload, max(uploaded_at)::date as last_upload
        from marts.mart_report_files group by 1 order by 1""",
    "file_issues": """
        select file_name, source_url, extract_status as status,
               coalesce(known_issue, extract_note) as note
        from marts.mart_report_files
        where extract_status = 'failed' or extract_note like '%shifted%'
           or extract_note like '%inconsistent%' or extract_note like '%used header%'
        order by uploaded_at desc""",
    "latest_sources": """
        select series_code, max(period_date) filter (where island = 'USVI') as latest_month,
               arg_max(source_file, source_uploaded_at) as file,
               arg_max(source_url, source_uploaded_at) as url
        from marts.fct_tourism_monthly group by 1 order by 1""",
}


def default(o):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    return float(o)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    changed = False
    for name, sql in QUERIES.items():
        rel = con.sql(sql)
        rows = [dict(zip(rel.columns, r)) for r in rel.fetchall()]
        text = json.dumps(rows, default=default, separators=(",", ":"))
        path = OUT / f"{name}.json"
        if not path.exists() or path.read_text() != text:
            path.write_text(text)
            changed = True
        print(f"dashboard/data/{name}.json  {len(rows)} rows")
    recon = con.sql("""select count(*), count(*) filter (where status like 'reconciled%')
                       from marts.mart_reconciliation""").fetchall()[0]
    tot = con.sql("""select count(*), count(*) filter (where was_revised)
                     from marts.fct_tourism_monthly""").fetchall()[0]
    files = con.sql("""select count(*), count(*) filter (where extract_status='ok')
                       from marts.mart_report_files""").fetchall()[0]
    meta_path = OUT / "meta.json"
    old_built = json.loads(meta_path.read_text()).get("built_at") if meta_path.exists() else None
    meta = {
        "files": files[0], "files_read": files[1],
        "values": tot[0], "values_revised": tot[1],
        "ytd_checks": recon[0], "ytd_checks_reconciled": recon[1],
        "built_at": datetime.now().isoformat(timespec="minutes") if changed or not old_built else old_built,
    }
    meta_path.write_text(json.dumps(meta, default=default))
    print("dashboard/data/meta.json")


if __name__ == "__main__":
    main()
