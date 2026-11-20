"""Run every step in order. This is what the monthly schedule calls.

    python run_pipeline.py            # full run
    python run_pipeline.py --from 3   # start at step 3 (skip discovery + download)
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STEPS = [
    (1, "Discover reports", [sys.executable, "pipeline/step1_discover.py"]),
    (2, "Download reports", [sys.executable, "pipeline/step2_download.py"]),
    (3, "Extract numbers", [sys.executable, "pipeline/step3_extract.py"]),
    (4, "Load DuckDB", [sys.executable, "pipeline/step4_load.py"]),
    (5, "dbt build (models + tests)", ["dbt", "build", "--profiles-dir", "."]),
    (6, "Export dashboard data", [sys.executable, "pipeline/step6_export.py"]),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=1)
    args = ap.parse_args()
    for n, label, cmd in STEPS:
        if n < args.start:
            continue
        print(f"\n=== Step {n}: {label} ===", flush=True)
        # dbt resolves the DuckDB path relative to where it runs, so run it inside dbt/
        cwd = ROOT / "dbt" if cmd[0] == "dbt" else ROOT
        result = subprocess.run(cmd, cwd=cwd, env=os.environ.copy())
        if result.returncode != 0:
            print(f"Step {n} failed - stopping so bad data never reaches the dashboard.")
            sys.exit(result.returncode)
    print("\nAll steps finished.")


if __name__ == "__main__":
    main()
