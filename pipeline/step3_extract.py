"""Step 3 - Extract: turn each one-page report into rows of numbers.

Every monthly report is the same table:

                 ST. THOMAS/ST. JOHN     ST. CROIX           U.S.V.I., TOTAL
    Period       2025   2026  % chg.     2025  2026 % chg.   2025   2026  % chg.
    YEAR TO DATE:
    AUGUST       ...
    MONTH:
    January      69,335 74,844  7.9      22,464 16,690 -25.7  91,799 91,534 -0.3
    ...

Reading the text top-to-bottom breaks on older files (cells merge, blank months are
skipped), so we read each word together with its position on the page instead:

1. The header row with six 4-digit years tells us where each column ends (numbers are
   right-aligned) and which year it holds.
2. The island labels (THOMAS, CROIX, U.S.V.I.) tell us which island each pair of year
   columns belongs to.
3. Every row whose label is a month name becomes 6 values (3 islands x 2 years). The
   "% chg." columns are skipped - we recompute change ourselves in dbt.

We also capture the printed YEAR TO DATE and ANNUAL TOTAL rows. They are not used for
the numbers - they let dbt check that our monthly values add up to what USVIBER printed.

Output: data/interim/observations_raw.csv (one row per number) and
        data/interim/extract_log.csv (one row per file, with any problem found)
"""
import csv
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "raw" / "manifest.csv"
PDF_DIR = ROOT / "data" / "raw" / "pdfs"
OUT = ROOT / "data" / "interim" / "observations_raw.csv"
LOG = ROOT / "data" / "interim" / "extract_log.csv"

MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
          "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
YEAR = re.compile(r"^(19|20)\d{2}$")
NUMBER = re.compile(r"^-?[\d,]*\.?\d+$")
ISLAND_WORDS = {"THOMAS": "STT_STJ", "THOMAS/ST.": "STT_STJ", "CROIX": "STX",
                "U.S.V.I.,": "USVI", "U.S.V.I.": "USVI", "U.S.V.I": "USVI"}


def lines(words, tol=4.5):
    """Group words into lines: words whose vertical position is within `tol` points."""
    rows = []
    for w in sorted(words, key=lambda w: (w[1], w[0])):
        if rows and abs(rows[-1][0] - w[1]) <= tol:
            rows[-1][1].append(w)
        else:
            rows.append([w[1], [w]])
    return [sorted(r[1], key=lambda w: w[0]) for r in rows]


# Words that must appear in the report title, so a file uploaded under the wrong name
# (it happens: CS24-NOV.pdf is really an employment report) is skipped, not loaded.
TITLE_WORDS = {"A": "AIR VISITOR", "CP": "CRUISE PASSENGER", "CS": "CRUISE SHIP",
               "H": "OCCUPANCY RATE", "RA": "AVAILABLE", "RN": "OCCUPIED"}
TITLE = re.compile(r"JANUARY\s+(\d{4})\s+(?:to|-|through)\s+[A-Z]+\s+(\d{4})", re.I)


def find_columns(words, name_year=None):
    """Return ([(right_edge_x, year, island)] for the six value columns, header_y, note)."""
    # Column positions: the top-most line holding six 4-digit years.
    best = None
    for ln in lines(words):
        if sum(bool(YEAR.match(w[4])) for w in ln) == 6:
            best = ln
            break
    if best is None:
        raise ValueError("could not find the header row with six year columns")
    header_years = [int(w[4]) for w in best if YEAR.match(w[4])]
    xs = [w[2] for w in best if YEAR.match(w[4])]
    header_y = best[0][1]
    # Column years. Three clues, each occasionally wrong in USVIBER's files:
    #   header years (e.g. 2025 2026 2025 2026 2025 2026), the title line
    #   ("JANUARY 2025 to AUGUST 2026") and the year in the file name (A26-AUG).
    # A clue is usable when it reads "previous year, current year". We use the header
    # when usable, otherwise the title, and log every disagreement.
    def usable(prev, cur):
        return cur == prev + 1
    hdr_ok = header_years[0::2] == [header_years[0]] * 3 and \
        header_years[1::2] == [header_years[1]] * 3 and usable(header_years[0], header_years[1])
    title = TITLE.search(" ".join(w[4] for w in words if w[1] < header_y))
    t_prev, t_cur = (int(title.group(1)), int(title.group(2))) if title else (None, None)
    title_ok = title is not None and usable(t_prev, t_cur)
    notes = []
    if hdr_ok:
        prev, cur = header_years[0], header_years[1]
        if title and (t_prev, t_cur) != (prev, cur):
            notes.append(f"title says {t_prev}-{t_cur}, header says {prev}-{cur}; used header")
    elif title_ok:
        prev, cur = t_prev, t_cur
        notes.append(f"header years {header_years} inconsistent; used title {prev}-{cur}")
    else:
        raise ValueError(f"no usable column years (header {header_years}, title {t_prev}-{t_cur})")
    if name_year and name_year != cur:
        notes.append(f"file name says {name_year}, report says {cur}")
    years = [prev, cur] * 3
    note = "; ".join(notes)
    # Island labels sit just above the year row, left to right.
    labels = sorted({(w[0], ISLAND_WORDS[w[4]]) for w in words
                     if w[4] in ISLAND_WORDS and header_y - 60 < w[1] < header_y})
    seen = []
    for _, isl in labels:
        if isl not in seen:
            seen.append(isl)
    if sorted(seen) != ["STT_STJ", "STX", "USVI"]:
        raise ValueError(f"could not find the three island labels, found {seen}")
    cols = [(x, yr, seen[i // 2]) for i, (x, yr) in enumerate(zip(xs, years))]
    return cols, header_y, note


def to_number(s):
    return float(s.replace(",", ""))


def extract(path: Path, name_year=None, series_code=None):
    page = pymupdf.open(path)[0]
    words = page.get_text("words")  # (x0, y0, x1, y1, text, ...)
    if not words:
        raise ValueError("scanned image with no text layer (cannot be read without OCR)")
    cols, header_y, note = find_columns(words, name_year)
    top = " ".join(w[4] for w in words if w[1] < header_y).upper()
    if series_code and TITLE_WORDS[series_code] not in top:
        raise ValueError(f"title does not mention '{TITLE_WORDS[series_code]}' - wrong file uploaded under this name")
    out, cells = [], {}
    section = None
    for ln in lines(words):
        if ln[0][1] <= header_y:
            continue
        label = " ".join(w[4] for w in ln if w[2] < cols[0][0] - 40).strip()
        up = label.upper().rstrip(":")
        if up.startswith("YEAR TO DATE") or up.startswith("TOTAL YEAR TO DATE"):
            section = "ytd"
        elif up.startswith("MONTH"):
            section = "month"
        elif up.startswith("QUARTER"):
            section = "quarter"
        if up.startswith("ANNUAL"):
            kind, month = "annual", 12
        elif up in MONTHS and label != up:  # monthly rows are Title case: "January"
            kind, month = "month", MONTHS.index(up) + 1
        elif up in MONTHS and section == "ytd":  # the YTD row is UPPER case: "AUGUST"
            kind, month = "ytd", MONTHS.index(up) + 1
        else:
            continue
        for w in ln:
            if not NUMBER.match(w[4]):
                continue
            # Hotel tables print every value with one decimal (73.8, 507.5). A bare
            # "2025" on the same line is a chart label, not a value.
            if series_code in ("H", "RA", "RN") and "." not in w[4]:
                continue
            # nearest column by right edge; ignore anything not lined up with one
            x, yr, isl = min(cols, key=lambda c: abs(c[0] - w[2]))
            if abs(x - w[2]) > 8:
                continue
            cell = (kind, month, yr, isl)
            cells.setdefault(cell, []).append(w[4])
    # One number per cell. If a chart label such as "2025" sits on the same line and
    # lands in a column, drop the year-looking token; anything else is a real problem.
    for (kind, month, yr, isl), texts in cells.items():
        if len(texts) > 1:
            texts = [t for t in texts if not YEAR.match(t)]
        if len(texts) != 1:
            raise ValueError(f"{len(texts)} values in one cell ({kind} {month}/{yr} {isl})")
        out.append({"row_kind": kind, "period_month": month, "column_year": yr,
                    "island": isl, "value_text": texts[0], "value": to_number(texts[0])})
    if not any(r["row_kind"] == "month" for r in out):
        raise ValueError("no monthly rows found")
    return out, note


def resolve_mislabeled_years(obs, log):
    """Some files print last year's labels on this year's numbers (RN26-JUN.pdf says
    "2024 / 2025" but holds 2025 / 2026 data). When a file's name and its printed years
    disagree, we try both readings and keep the one whose numbers match the same months
    in correctly labelled files. Numbers are a better witness than labels."""
    flagged = {x["media_id"]: x for x in log if "file name says" in x["note"]}
    if not flagged:
        return obs
    known = {}
    for o in obs:
        if o["media_id"] not in flagged and o["row_kind"] == "month":
            key = (o["series_code"], o["period_month"], o["column_year"], o["island"])
            known.setdefault(key, set()).add(o["value"])
    for mid, entry in flagged.items():
        mine = [o for o in obs if o["media_id"] == mid]
        m = re.search(r"file name says (\d{4}), report says (\d{4})", entry["note"])
        shift = int(m.group(1)) - int(m.group(2))

        def hits(offset):
            return sum(o["value"] in known.get((o["series_code"], o["period_month"],
                                                o["column_year"] + offset, o["island"]), ())
                       for o in mine if o["row_kind"] == "month")
        as_printed, as_named = hits(0), hits(shift)
        if as_named > as_printed:
            for o in mine:
                o["column_year"] += shift
            entry["note"] += f"; numbers match the file-name years ({as_named} vs {as_printed} matches) - shifted {shift:+d} year"
        else:
            entry["note"] += f"; numbers match the printed years ({as_printed} vs {as_named} matches) - kept"
    return obs


def main():
    manifest = list(csv.DictReader(MANIFEST.open()))
    obs, log = [], []
    for r in manifest:
        path = PDF_DIR / f"{r['media_id']}_{r['file_name']}"
        try:
            rows, note = extract(path, int(r["name_year"]), r["series_code"])
            status = "ok"
        except Exception as e:  # keep going; the log + a dbt test make problems visible
            rows, status, note = [], "failed", str(e)
        for x in rows:
            obs.append({"media_id": r["media_id"], "series_code": r["series_code"], **x})
        log.append({"media_id": r["media_id"], "file_name": r["file_name"],
                    "status": status, "values": len(rows), "note": note})
    obs = resolve_mislabeled_years(obs, log)
    fields = ["media_id", "series_code", "row_kind", "period_month", "column_year",
              "island", "value_text", "value"]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(obs)
    with LOG.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(log[0].keys()))
        w.writeheader()
        w.writerows(log)
    failed = [x for x in log if x["status"] != "ok"]
    print(f"{len(obs)} values from {len(log) - len(failed)} files; {len(failed)} files could not be read.")
    for x in failed:
        print(f"  {x['file_name']}: {x['note']}")


if __name__ == "__main__":
    main()
