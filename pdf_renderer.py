"""PDF rendering via Playwright headless Chromium."""

from __future__ import annotations
import os
from pathlib import Path

_CHROMIUM_CANDIDATES = [
    os.environ.get("PLAYWRIGHT_CHROMIUM_PATH", ""),
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
    "/opt/pw-browsers/chromium/chrome-linux/chrome",
    "/usr/bin/chromium-browser",
    "/usr/bin/chromium",
    "/usr/bin/google-chrome",
]


def _find_chromium():
    for p in _CHROMIUM_CANDIDATES:
        if p and Path(p).exists():
            return p
    return None


class PdfRenderer:
    def __init__(self, page_format="A4", print_background=True, margin=None):
        self.page_format = page_format
        self.print_background = print_background
        self.margin = margin or {"top": "1.5cm", "bottom": "1.5cm", "left": "1.5cm", "right": "1.5cm"}
        self._executable = _find_chromium()

    def render_topics(self, topics_html, progress_cb=None):
        from playwright.sync_api import sync_playwright
        launch_kwargs = {
            "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        }
        if self._executable:
            launch_kwargs["executable_path"] = self._executable
        results = []
        total = len(topics_html)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(**launch_kwargs)
            try:
                for i, html in enumerate(topics_html):
                    page = browser.new_page()
                    try:
                        page.set_content(html, wait_until="networkidle", timeout=30_000)
                        results.append(page.pdf(
                            format=self.page_format,
                            print_background=self.print_background,
                            margin=self.margin,
                        ))
                    except Exception:
                        results.append(b"")
                    finally:
                        page.close()
                    if progress_cb:
                        progress_cb(i + 1, total)
            finally:
                browser.close()
        return results
