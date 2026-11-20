# USVI Tourism Data Warehouse: Step-by-Step Guide

Portfolio project 02 · Crucian Data Works · Roger Simon

This guide walks through the project in the order it was built. Each step says what the goal is, why it is done that way, the command to run, and what you should see. If you follow it from top to bottom you can rebuild the whole thing yourself and explain every decision in an interview or a client meeting.

Source data: the monthly tourism reports published by the [USVI Bureau of Economic Research (USVIBER)](https://usviber.org/). The project is an independent analysis, not an official USVIBER publication.

---

## The big picture

USVIBER posts the territory's tourism numbers every month as one-page PDF tables: air visitor arrivals, cruise passengers, cruise ship calls, hotel occupancy and hotel room nights. There is no download button for a spreadsheet, and each new PDF reprints (and often revises) the previous year's months.

The project turns those PDFs into a small, tested data warehouse:

```
usviber.org media feed ──► 1 discover ──► 2 download ──► 3 extract ──► 4 load (DuckDB)
                                                                           │
                    dashboard ◄── 6 export JSON ◄── 5 dbt models + tests ◄─┘
```

The difference from project 01 (the beach tracker) is the modelling. Here the same month shows up in many files with different values, so the warehouse has to decide which number is "the" number, keep the history of revisions, and cross-check tables that should agree with each other.

### Final results

| Measure | Result |
|---|---|
| Report PDFs found | 281 (54 air, 61 cruise passenger, 51 ship call, 43 occupancy, 34 rooms available, 38 rooms occupied) |
| PDFs read | 278. The other 3 are documented and have corrected replacements |
| Values extracted (every cell in every file) | 18,684 |
| Monthly values in the warehouse | 1,730 (one per measure, island and month) |
| Values revised after first publication | 614 |
| dbt checks | 30 data tests, 28 pass, 2 warnings that are real findings |
| Matches usviber.org headline numbers | Air arrivals Jan–Aug 2026: 744,448 vs 744,449 printed. Cruise: 1,493,974, exact |

Coverage: cruise passengers from January 2015, air arrivals from January 2017, ship calls from January 2018, hotel occupancy and room nights occupied from January 2020, room nights available from January 2021. Arrivals run through August 2026 and hotels through June 2026.

---

## Step 0: Set up your machine

**Goal:** a working Python environment with the tools installed.

**Why:** a virtual environment (`.venv`) keeps this project's libraries apart from everything else on the computer.

```bash
cd usvi-tourism-warehouse
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
dbt --version                      # should print dbt-core and the duckdb adapter
```

| Tool | Job in this project |
|---|---|
| `requests` | Calls the USVIBER media feed and downloads the PDFs |
| `pymupdf` | Reads each word on a PDF page together with its x/y position |
| `duckdb` | A database in one file. No server to install |
| `dbt` | Runs the SQL models in the right order and tests the results |
| `pandas` | Used by the export step to shape JSON for the dashboard |

### Project layout

```
usvi-tourism-warehouse/
├── run_pipeline.py            # runs steps 1-6 in order
├── pipeline/                  # one Python file per step
├── data/raw/manifest.csv      # every report file found (step 1)
├── data/raw/pdfs/             # the downloaded PDFs (not stored in git)
├── data/interim/              # every extracted number as CSV (step 3)
├── warehouse/tourism.duckdb   # the database (rebuilt every run, not in git)
├── dbt/                       # SQL models, tests, seeds, macros
├── dashboard/                 # the web page and its JSON data
└── .github/workflows/         # the twice-monthly schedule
```

---

## Step 1: Discover every report

**File:** `pipeline/step1_discover.py` · **Output:** `data/raw/manifest.csv`

**Goal:** a list of every monthly tourism PDF USVIBER has posted, with its URL and upload date.

**Why:** usviber.org runs on WordPress. Every WordPress site has a public "media library" feed at `/wp-json/wp/v2/media` that lists each uploaded file as JSON. That is far more complete and reliable than clicking through web pages. The feed has about 1,150 files across 12 pages, covering all of the bureau's uploads, not only tourism.

USVIBER names its tourism reports with a short code, a two-digit year and a month:

| Code | Report | Example |
|---|---|---|
| `A` | Air visitor arrivals | `A26-AUG.pdf` |
| `CP` | Cruise passenger arrivals | `CP26-AUG.pdf` |
| `CS` | Cruise ship calls | `CS26-AUG.pdf` |
| `H` | Hotel occupancy rate (%) | `H26-JUN.pdf` |
| `RA` | Hotel room nights available (thousands) | `RA26-JUN.pdf` |
| `RN` | Hotel room nights occupied (thousands) | `RN26-JUN.pdf` |

The names are not perfectly consistent (`h23-decR`, `CS25-SEPT-1`, `CP24-Aug`), so the filter is a regular expression that tolerates case, separators and suffixes:

```python
NAME = re.compile(r"^(A|CP|CS|H|RA|RN)(\d{2})[-_ ]?([A-Za-z]{3})", re.I)
```

Read it as: one of the six codes, then two digits, then an optional dash, underscore or space, then three letters for the month.

```bash
python pipeline/step1_discover.py
```

**What you should see:** `281 report files` and a manifest with the columns `media_id`, `file_name`, `uploaded_at`, `series_code`, `series`, `name_year`, `name_month` and `url`.

The feed only reaches back to uploads from 2022. That is fine: every report reprints the previous year as well as the current one, and the January–December annual tables go further back, which is why cruise passengers start in 2015.

---

## Step 2: Download the PDFs

**File:** `pipeline/step2_download.py` · **Output:** `data/raw/pdfs/`, `data/raw/downloads.csv`

**Goal:** a local copy of each PDF, downloaded only once.

**Why:** being polite to a small government website matters. The script skips files it already has, pauses half a second between requests, identifies itself with a contact address in the User-Agent, and records a SHA-256 fingerprint of each file so a silently replaced file can be spotted later. Files are saved as `{media_id}_{file_name}` because USVIBER sometimes uploads two different files with the same name.

```bash
python pipeline/step2_download.py
```

**What you should see:** 281 files in `data/raw/pdfs/` (about 100 MB). Run it again and it finishes in a second with nothing new to fetch.

---

## Step 3: Extract the numbers

**File:** `pipeline/step3_extract.py` · **Output:** `data/interim/observations_raw.csv`, `data/interim/extract_log.csv`

**Goal:** every number in every table, tagged with its measure, island, year, month and row type.

### How a report is laid out

Each one-page report has a title such as "AIR VISITOR ARRIVALS, JANUARY 2025 to AUGUST 2026", then a header with six year columns grouped in pairs by island: St. Thomas/St. John, St. Croix and the territory (USVI) total. Below are sections for year-to-date, monthly rows (January, February, ...), quarters and the annual total.

### Reading by position, not by text order

PDF text does not come out in reading order, so the script asks PyMuPDF for every word and its box (`x0, y0, x1, y1`). Then it:

1. Groups words into lines when their vertical positions are within 4.5 points.
2. Finds the header: the topmost line with six year values. The island names just above it say which pair of columns belongs to which island.
3. For each row whose label is a month name, assigns each number to the nearest column by its right edge, since numbers are right-aligned. A number more than 8 points from any column is ignored.
4. Tells month rows from year-to-date rows by case. Monthly rows print "January"; the year-to-date line prints "AUGUST".

```bash
python pipeline/step3_extract.py
```

**What you should see:** about 18,700 values from 278 files, and three files reported as unreadable.

### The problems we hit, and how we solved them

This is where most of the time went. Each fix is a rule in the code with a comment explaining it.

| Problem | Example | Rule |
|---|---|---|
| A scanned image with no text | `A20-dec.pdf` | Raise a clear error. A text version `A20-DEC.pdf` exists, and a dbt seed lists this file as a known exception |
| The wrong report uploaded under a name | `A23-NOV.pdf` holds hotel occupancy; `CS24-NOV.pdf` holds civilian employment | Check that the title contains the expected words ("AIR VISITOR", "CRUISE SHIP"...). Corrected `-1` files exist for both |
| Last year's labels on this year's numbers | `RN26-JUN.pdf` and `RN26-MAR.pdf` print 2024/2025 but hold 2025/2026 data; same for `RN23-APRIL` and `RA23-APRIL` | Try both readings and keep the one whose numbers match the same months in correctly labelled files (25 matches vs 3). Numbers are a better witness than labels |
| Header years in the wrong order | `RN23-JUN`, `JUL`, `NOV`, `DEC` print `2022 2023 2021 2022 2021 2022` | A valid header reads A, A+1 repeated three times. If it does not, use the years in the title |
| A typo in the title | `CP24-Aug` to `CP24-DEC` say "2023 to 2023" | Trust the header when it is valid |
| Chart labels on the same line as values | A bare "2025" next to `73.8` on hotel tables | Hotel values always have one decimal, so only accept numbers with a "." for H, RA and RN; drop year-looking tokens if a cell gets two values |

Every adjustment is written to `extract_log.csv`, so nothing is fixed silently. The dashboard's "What the tests caught" panel reads from this log.

---

## Step 4: Load into DuckDB

**File:** `pipeline/step4_load.py` · **Output:** `warehouse/tourism.duckdb`

**Goal:** put the manifest and the extracted values into a database, unchanged, in a schema called `raw`.

**Why:** the raw layer is a faithful copy of what came out of the PDFs. All cleaning and business rules happen in dbt, where they are visible, versioned and tested. If a rule turns out to be wrong you change one SQL file and rebuild; you never have to re-read the PDFs.

```bash
python pipeline/step4_load.py
```

**What you should see:** `raw.report_files` (281 rows) and `raw.observations` (18,684 rows).

---

## Step 5: Model and test with dbt

**Folder:** `dbt/` · **Run:** `cd dbt && dbt build --profiles-dir .`

`dbt build` creates every model in dependency order and runs the tests right after the models they cover. If a test with error severity fails, the pipeline stops and the dashboard keeps its last good data.

### The layers

| Layer | Model | What it does |
|---|---|---|
| Seeds | `series`, `islands`, `known_unreadable_files` | Small reference tables kept in CSV: names and units of each measure, island names, the three files we know cannot be read |
| Staging | `stg_report_files`, `stg_observations` | Rename columns, set types, build a proper `period_date` |
| Intermediate | `int_monthly_versions` | Every copy of every monthly value, ranked by upload date |
| Fact | `fct_tourism_monthly` | One row per measure, island and month: the latest value, the first published value, and whether it was revised |
| Marts | `mart_island_monthly`, `mart_annual` | Wide tables for the dashboard. Territory room nights are the sum of the two islands |
| Checks | `mart_reconciliation`, `mart_occupancy_check`, `mart_island_consistency`, `mart_revisions`, `mart_report_files` | Tables whose only job is to find problems |

### The key idea: one month, many versions

Each new report reprints last year's months, and USVIBER revises them as late survey returns arrive. March 2023 cruise passengers appears in 33 different files. So the model ranks the copies with two window functions:

```sql
row_number() over (partition by series_code, island, period_date
                   order by uploaded_at)          as version_number,   -- 1 = first published
row_number() over (partition by series_code, island, period_date
                   order by uploaded_at desc) = 1 as is_latest         -- the number we report
```

The fact table keeps `is_latest` rows but joins back the `version_number = 1` value, so a revision is recorded instead of overwritten. That is how we know 614 of 1,730 values changed after first publication. For example, May 2025 air arrivals were first printed as 92,785 and later revised to 80,107, and March 2023 cruise passengers went from 167,377 to 207,392.

### Cross-checks between tables

Two of the marts compare numbers that should agree:

- Occupancy rate vs room nights. Table H prints the occupancy rate. Room nights occupied ÷ room nights available should give the same rate. `mart_occupancy_check` flags any month where they differ by more than 3 points.
- Islands vs territory. St. Thomas/St. John plus St. Croix should equal the USVI total. `mart_island_consistency` flags gaps.

### Tests

The 30 data tests fall into four groups:

| Kind | Examples |
|---|---|
| Structure | `not_null`, accepted values for codes and islands, one row per measure/island/month (`dbt_unique_combination` macro) |
| Ranges | Occupancy between 0 and 100, arrivals never negative (`dbt_expect_between` macro) |
| Completeness | `assert_no_month_gaps`: every month present from each series' start, with one documented exception, October 2017 cruise passengers (ports closed after Hurricane Maria) |
| Truth checks | `assert_latest_reports_reconcile`: in the newest air, cruise and ship-call reports, the monthly rows add up to the printed year-to-date total. `assert_matches_usviber_homepage_2026_08`: our Jan–Aug 2026 totals match the usviber.org homepage within 2 visitors. `assert_unreadable_files_are_known`: no new unreadable file can slip through unnoticed |

Two tests are set to warn rather than fail, because what they find is a problem in the source data, not in our pipeline:

- 8 island-months since January 2025 where the printed occupancy rate and room nights disagree;
- 41 island-vs-territory gaps, mostly in rooms available.

The homepage test also warns rather than fails, because a later USVIBER revision can legitimately move those totals.

**What you should see:**

```
Done. PASS=42 WARN=2 ERROR=0 SKIP=0 TOTAL=44
```

The 44 is everything dbt built: 3 seeds, 11 models and 30 tests.

### What the tests found

These are the findings worth talking about:

1. June 2026 hotel occupancy. Table H ([H26-JUN.pdf](https://usviber.org/wp-content/uploads/2026/07/H26-JUN.pdf)) prints 73.8% for the territory, and so does the usviber.org homepage. The room-night tables give 44.1%, and USVIBER's own detailed hotel table for that month (TABLE26-JUN.pdf) also says 44.1%. St. Croix shows 63.1% printed vs 35.0% computed. The headline figure is likely a typo. The dashboard shows both and uses the room-night rate for its year-to-date figure.
2. Islands that don't add up. In [A26-AUG.pdf](https://usviber.org/wp-content/uploads/2026/09/A26-AUG.pdf), April 2026 air arrivals are 106,083 for the territory but 81,705 + 13,034 = 94,739 for the islands. December 2021 (A22-DEC.pdf) is 85,741 vs 53,931. August 2022 ship calls (CS23-DEC.pdf) are 22 vs 16.
3. Year-to-date lines with typos. Only 871 of 1,038 year-to-date lines (84%) equal the sum of their monthly rows. In [CP26-AUG.pdf](https://usviber.org/wp-content/uploads/2026/09/CP26-AUG.pdf) the island year-to-date lines are wrong, but the territory total is right. The newest report for each count series always reconciles for the territory, which is what the error-severity test enforces.
4. Big revisions. Cruise passengers for early 2023 were revised up 11–24%, and ship calls for the same months up 15–28%.

---

## Step 6: Export for the dashboard

**File:** `pipeline/step6_export.py` · **Output:** `dashboard/data/*.json`

**Goal:** small JSON files the web page can load directly, with no server or database behind it.

| File | Contents |
|---|---|
| `monthly.json` | One row per island and month: air, cruise, calls, occupancy, room nights |
| `annual.json` | Yearly totals, with how many months each year has |
| `revisions.json` | The largest revisions after first publication |
| `occupancy_flags.json`, `island_flags.json` | The cross-check findings |
| `file_issues.json`, `files.json` | What happened to each file, counts per series |
| `latest_sources.json`, `meta.json` | Newest report per series and headline counts |

```bash
python pipeline/step6_export.py
cd dashboard && python -m http.server 8000
# open http://localhost:8000
```

The dashboard uses plain HTML, CSS and JavaScript with Chart.js. It has an island switch, year-to-date KPIs against the same months last year, monthly arrivals, a seasonality heatmap, annual totals, published vs computed hotel occupancy, passengers per ship call, and the data-quality panel.

---

## Step 7: Run everything with one command

```bash
python run_pipeline.py            # all six steps
python run_pipeline.py --from 3   # skip discovery and download, re-read the PDFs you have
python run_pipeline.py --from 5   # only rebuild dbt and the JSON
```

If any step fails, the script stops so bad data never reaches the dashboard.

---

## Step 8: Schedule it monthly

**File:** `.github/workflows/monthly.yml`

GitHub Actions runs the pipeline at 9:00 AM St. Croix time on the 5th and the 20th of every month. USVIBER usually posts the previous month's reports in the first weeks of a month, so the second run catches late uploads. Each run:

1. Installs Python and the requirements.
2. Restores the PDFs from the previous run's cache, so only new reports are downloaded.
3. Runs `python run_pipeline.py`.
4. Commits the refreshed manifest, extracted CSVs and dashboard JSON back to the repository.
5. Uploads the dashboard to cruciandataworks.com over FTP, but only once the FTP secrets exist.
6. If anything fails, opens or updates a GitHub issue labelled `refresh-failure` and assigns it to you. GitHub emails the assignee.

To test the alert: Actions tab → Monthly tourism data refresh → Run workflow → tick "Fail on purpose".

Settings the workflow uses (Settings → Secrets and variables → Actions):

| Name | Type | Value |
|---|---|---|
| `FTP_SERVER` | Secret | `ftp.cruciandataworks.com` |
| `FTP_USERNAME` | Secret | Your Hostinger FTP user |
| `FTP_PASSWORD` | Secret | Your Hostinger FTP password |
| `FTP_SERVER_DIR` | Variable | `/public_html/projects/tourism-warehouse/` |

---

## Talking about this project

A 30-second version:

> USVIBER publishes the territory's tourism numbers as monthly PDFs, and every new report revises the previous year. I built a pipeline that reads all 281 reports through the bureau's WordPress feed, extracts every number by its position on the page, and models it in dbt and DuckDB so each month keeps its latest value and its revision history. Thirty data tests check the result against USVIBER's own headline totals and cross-check the tables against each other. That surfaced misnamed files, reports printed with last year's labels, island figures that don't add to the territory total, and a June 2026 hotel occupancy rate of 73.8% that the bureau's room-night tables put at 44.1%.

Questions you can expect, with short answers:

- Why not just use the latest PDF? It only covers about 20 months, and older months get revised. Reading every report gives a longer history and shows how much the numbers move.
- Why DuckDB? The data is small, and a single-file database runs anywhere, including GitHub Actions, with no server or cost.
- Why keep revisions? A client who reported May 2025 air arrivals as 92,785 needs to know the official number is now 80,107.
- What would you do next? Ask USVIBER about the June 2026 occupancy figure, add OCR for the one scanned file, and add visitor spending once a consistent source is found.

---

## Publishing to cruciandataworks.com

The dashboard is published at `cruciandataworks.com/projects/tourism-warehouse/`. The monthly workflow uploads `dashboard/` there after each refresh, and the homepage Projects section links to it with a card for Project 02.
