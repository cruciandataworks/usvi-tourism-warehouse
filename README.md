# USVI Tourism Data Warehouse

Portfolio project 02 from [Crucian Data Works](https://cruciandataworks.com). It covers ten years of U.S. Virgin Islands tourism numbers: air visitor arrivals, cruise passengers, cruise ship calls, hotel occupancy and room nights. They are read from 281 monthly PDF reports published by the [USVI Bureau of Economic Research](https://usviber.org/) and modelled into a tested dbt + DuckDB warehouse.

Live dashboard: https://cruciandataworks.com/projects/tourism-warehouse/

## What it does

1. Discover: lists every tourism report through usviber.org's public WordPress media feed.
2. Download: caches each PDF once, with SHA-256 fingerprints.
3. Extract: reads every number by its position on the page (PyMuPDF), with documented fixes for mislabelled years and misnamed files.
4. Load: raw values go into DuckDB.
5. Model and test (dbt): keeps the newest printed value for each month together with its first published value, then cross-checks occupancy against room nights and islands against territory totals. 30 data tests.
6. Export: writes JSON for a static dashboard. GitHub Actions refreshes it on the 5th and 20th of each month.

## Findings

- 614 of 1,730 monthly values were revised after first publication.
- June 2026 hotel occupancy is printed as 73.8%, but room nights occupied ÷ available give 44.1%, which matches USVIBER's detailed hotel table.
- Some island figures don't add up to the territory total. For example, April 2026 air arrivals are 106,083 for the territory vs 94,739 for the islands.
- Three source files are unreadable or misnamed, and 17 print the wrong years. All are handled and logged.

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python run_pipeline.py
cd dashboard && python -m http.server 8000
```

The full walkthrough is in [docs/STEP_BY_STEP.md](docs/STEP_BY_STEP.md).

## Data credit

All figures come from public USVIBER reports. This is an independent analysis, not an official USVIBER publication. For official statistics, see [usviber.org](https://usviber.org/).

© Crucian Data Works, LLC · Roger Simon · hello@cruciandataworks.com
