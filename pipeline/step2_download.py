"""Step 2 - Download: save a copy of every report PDF listed in the manifest.

Two habits worth learning here:
1. Idempotent: running it twice doesn't download twice. Files we already have are skipped,
   so the monthly run only fetches new reports.
2. Fingerprints: we record a SHA-256 hash of each file. If USVIBER silently replaces a PDF
   (USVIBER often re-uploads revised reports), the hash changes and we can tell.

Output: data/raw/pdfs/*.pdf and data/raw/downloads.csv
"""
import csv
import hashlib
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "raw" / "manifest.csv"
PDF_DIR = ROOT / "data" / "raw" / "pdfs"
LOG = ROOT / "data" / "raw" / "downloads.csv"
HEADERS = {"User-Agent": "CrucianDataWorks-portfolio/1.0 (hello@cruciandataworks.com)"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader(MANIFEST.open()))
    log, new, failed = [], 0, 0
    for r in rows:
        # Prefix with media id so two uploads with the same name can't overwrite each other
        target = PDF_DIR / f"{r['media_id']}_{r['file_name']}"
        if not target.exists():
            try:
                resp = requests.get(r["url"], headers=HEADERS, timeout=120)
                resp.raise_for_status()
                target.write_bytes(resp.content)
                new += 1
                time.sleep(0.5)
            except requests.RequestException as e:
                print(f"  FAILED {r['file_name']}: {e}")
                failed += 1
                continue
        log.append({"media_id": r["media_id"], "local_file": target.name,
                    "bytes": target.stat().st_size, "sha256": sha256(target)})
    with LOG.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["media_id", "local_file", "bytes", "sha256"])
        w.writeheader()
        w.writerows(log)
    print(f"{len(log)} PDFs on disk ({new} new this run, {failed} failed).")


if __name__ == "__main__":
    main()
