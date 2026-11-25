"""Add ?v=<content hash> to the dashboard's own CSS and JS links.

The web host tells browsers to keep .js and .css files for 7 days. Without a version
tag, a visitor can get a new index.html with last week's app.js, and new sections stay
blank. The tag changes only when the file's content changes, so normal caching still
works. Runs in the workflow right before the upload; safe to run any number of times.
"""
import hashlib
import re
from pathlib import Path

DASH = Path(__file__).resolve().parents[1] / "dashboard"


def stamp(page: Path) -> bool:
    html = page.read_text(encoding="utf-8")

    def tag(m):
        attr, name = m.group(1), m.group(2)
        f = page.parent / name
        if not f.is_file():
            return m.group(0)
        v = hashlib.sha256(f.read_bytes()).hexdigest()[:10]
        return f'{attr}="{name}?v={v}"'

    # local files only: no scheme, no leading slash
    new = re.sub(r'(href|src)="(?![a-z]+:|/)([^"?#]+\.(?:css|js))(?:\?v=[0-9a-f]+)?"', tag, html)
    if new != html:
        page.write_text(new, encoding="utf-8")
        return True
    return False


if __name__ == "__main__":
    for p in sorted(DASH.glob("*.html")):
        print(f"  {p.name}: {'stamped' if stamp(p) else 'already current'}")
