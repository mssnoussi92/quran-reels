"""Render the brand images of Quran Words Daily from brand.html (docs/profils.md).

    python assets/brand/src/render.py            # every image into assets/brand/
    python assets/brand/src/render.py avatar     # one of them

Needs Playwright's Chromium (a dependency of the project). Set CHROMIUM to a browser binary
to use another one (in a cloud session: /opt/pw-browsers/chromium).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
OUT = HERE.parent

# name: (width, height, file, transparent). Sizes: each platform's recommended upload.
FORMATS = {
    "avatar": (1080, 1080, "avatar-1080.jpg", False),           # all four platforms
    "facebook-cover": (1640, 624, "facebook-cover-1640x624.jpg", False),
    "youtube-banner": (2560, 1440, "youtube-banner-2560x1440.jpg", False),
    "watermark": (150, 150, "youtube-watermark-150.png", True),
}


def render(names: list[str]) -> None:
    with sync_playwright() as pw:
        exe = os.environ.get("CHROMIUM")
        browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        for name in names:
            w, h, file, transparent = FORMATS[name]
            page = browser.new_page(viewport={"width": w, "height": h})
            page.goto((HERE / "brand.html").as_uri() + f"?f={name}")
            page.wait_for_selector("body[data-ready='1']")
            out = OUT / file
            if transparent:
                page.screenshot(path=str(out), omit_background=True)
            else:
                page.screenshot(path=str(out), type="jpeg", quality=92)
            page.close()
            print(f"{name}: {out.relative_to(OUT.parent.parent)}")
        browser.close()


if __name__ == "__main__":
    asked = sys.argv[1:] or list(FORMATS)
    unknown = [n for n in asked if n not in FORMATS]
    if unknown:
        sys.exit(f"unknown format: {', '.join(unknown)} (known: {', '.join(FORMATS)})")
    render(asked)
