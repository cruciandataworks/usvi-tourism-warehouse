"""Step 4 - Load: copy the extracted CSVs into a DuckDB database file.

DuckDB is a database that lives in a single file (warehouse/tourism.duckdb) - no server to
install. It speaks normal SQL, so the same models would run on Snowflake or Databricks
with small changes.

We load into a schema called "raw" and change nothing. This is the "L" in ELT
(Extract, Load, Transform): load first, transform later inside the database with dbt.
Every row also gets a loaded_at timestamp so we know when it arrived.
"""
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "warehouse" / "tourism.duckdb"

TABLES = {
    "observations": ROOT / "data" / "interim" / "observations_raw.csv",
    "report_manifest": ROOT / "data" / "raw" / "manifest.csv",
    "report_downloads": ROOT / "data" / "raw" / "downloads.csv",
    "extract_log": ROOT / "data" / "interim" / "extract_log.csv",
}


def main():
    DB.parent.mkdir(exist_ok=True)
    con = duckdb.connect(str(DB))
    con.execute("create schema if not exists raw")
    for table, path in TABLES.items():
        # all_varchar: keep everything as text; typing happens in dbt staging models
        con.execute(f"""
            create or replace table raw.{table} as
            select *, current_timestamp as loaded_at
            from read_csv('{path}', header = true, all_varchar = true)
        """)
        n = con.execute(f"select count(*) from raw.{table}").fetchone()[0]
        print(f"raw.{table:18} {n:>6} rows")
    con.close()
    print(f"Database: {DB.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
