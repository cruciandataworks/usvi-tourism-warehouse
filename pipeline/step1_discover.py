"""Step 1 - Discover: list every monthly tourism report the USVI Bureau of Economic
Research (USVIBER) has published.

usviber.org runs on WordPress, which has a public "media library" feed listing every
uploaded file. USVIBER names its monthly one-page reports with a short code, a
two-digit year and a month, for example:

    A26-AUG.pdf     Air visitor arrivals, January 2025 to August 2026
    CP26-AUG.pdf    Cruise passenger arrivals
    CS26-AUG.pdf    Cruise ship calls
    H26-JUN.pdf     Hotel occupancy rate (%)
    RA26-JUN.pdf    Hotel room nights available (thousands)
    RN26-JUN.pdf    Hotel room nights occupied (thousands)

We read the whole feed (about 1,200 files) and keep only names that match that pattern.

Output: data/raw/manifest.csv - one row per report file.
"""
import csv
import re
import time
from pathlib import Path

import requests

API = "https://usviber.org/wp-json/wp/v2/media"
HEADERS = {"User-Agent": "CrucianDataWorks-portfolio/1.0 (hello@cruciandataworks.com)"}
OUT = Path(__file__).resolve().parents[1] / "data" / "raw" / "manifest.csv"

SERIES = {
    "A": "air_arrivals",
    "CP": "cruise_passengers",
    "CS": "cruise_ship_calls",
    "H": "hotel_occupancy_pct",
    "RA": "room_nights_available",
    "RN": "room_nights_occupied",
}
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
# code + 2-digit year + optional separator + month word, e.g. A26-AUG, h23-decR, CS25-SEPT-1
NAME = re.compile(r"^(A|CP|CS|H|RA|RN)(\d{2})[-_ ]?([A-Za-z]{3})", re.I)


def parse_name(name: str):
    m = NAME.match(name)
    if not m:
        return None
    code, yy, mon = m.group(1).upper(), int(m.group(2)), m.group(3).upper()
    if mon not in MONTHS:
        return None
    return code, 2000 + yy, MONTHS.index(mon) + 1


def fetch_all_pages():
    page, items = 1, []
    while True:
        r = requests.get(API, params={"per_page": 100, "page": page,
                                      "_fields": "id,date,source_url,mime_type"},
                         headers=HEADERS, timeout=60)
        if r.status_code == 400:  # WordPress: "no more pages"
            break
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        items.extend(batch)
        total_pages = int(r.headers.get("X-WP-TotalPages", page))
        print(f"  page {page}/{total_pages}: {len(batch)} files")
        if page >= total_pages:
            break
        page += 1
        time.sleep(1)  # be polite to a government server
    return items


def main():
    print("Reading USVIBER's media feed...")
    rows = []
    for it in fetch_all_pages():
        if it.get("mime_type") != "application/pdf":
            continue
        url = it["source_url"]
        name = url.rsplit("/", 1)[-1]
        parsed = parse_name(name)
        if not parsed:
            continue
        code, year, month = parsed
        rows.append({"media_id": it["id"], "file_name": name, "uploaded_at": it["date"],
                     "series_code": code, "series": SERIES[code],
                     "name_year": year, "name_month": month, "url": url})
    rows.sort(key=lambda r: (r["uploaded_at"], r["media_id"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["series_code"]] = counts.get(r["series_code"], 0) + 1
    print(f"Found {len(rows)} monthly report PDFs: {counts}")
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
