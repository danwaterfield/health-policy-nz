"""
NZ Health Survey fetcher.

Attempts to download the prevalence CSV from the NZHS Shiny app using Playwright.
Falls back to checking for a local file if Playwright fails or is unavailable.
"""
from pathlib import Path
from pipeline.config import RAW_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher


class NZHSFetcher(BaseFetcher):
    source_key = "nzhs_prevalence"

    def fetch(self, dry_run=False) -> Path:
        dest = RAW_DIR / SOURCES[self.source_key]["filename"]
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        if self.is_fresh(dest):
            self.log(f"Cache fresh: {dest}")
            return dest

        if dry_run:
            self.log(f"DRY RUN: would download NZHS prevalence CSV to {dest}")
            return dest

        self.log("Attempting Playwright download from NZHS Shiny app...")
        success = self._playwright_download(dest)

        if not success:
            if dest.exists():
                self.log("Playwright failed; using existing local file")
                return dest
            raise RuntimeError(
                "Playwright download failed and no local file found. "
                "Please manually download the NZHS prevalence CSV from "
                f"{SOURCES[self.source_key]['url']} and save it to {dest}"
            )

        self.strip_bom(dest)
        self.log(f"Downloaded to {dest}")
        return dest

    def _playwright_download(self, dest: Path) -> bool:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            self.log("Playwright not installed; skipping automated download")
            return False

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(accept_downloads=True)
                page = context.new_page()

                url = SOURCES[self.source_key]["url"]
                self.log(f"Navigating to {url}")
                page.goto(url, timeout=60000)

                # Wait for the Shiny app to load
                page.wait_for_load_state("networkidle", timeout=60000)

                # Look for download datasets tab / button
                # The NZHS app has a "Download datasets" tab
                try:
                    page.click("text=Download datasets", timeout=15000)
                    page.wait_for_load_state("networkidle", timeout=15000)
                except PWTimeout:
                    self.log("Could not find 'Download datasets' tab")
                    browser.close()
                    return False

                # Try to find and click the prevalence CSV download link
                try:
                    with page.expect_download(timeout=60000) as dl_info:
                        # Look for a download button/link for prevalence data
                        page.click("text=prevalence", timeout=10000)
                    download = dl_info.value
                    download.save_as(str(dest))
                    browser.close()
                    return True
                except PWTimeout:
                    pass

                # Alternative: look for any CSV download button
                try:
                    with page.expect_download(timeout=60000) as dl_info:
                        page.click("[data-testid='download'], .download-btn, a[download]", timeout=10000)
                    download = dl_info.value
                    download.save_as(str(dest))
                    browser.close()
                    return True
                except PWTimeout:
                    self.log("Could not trigger download from Shiny app")
                    browser.close()
                    return False

        except Exception as e:
            self.log(f"Playwright error: {e}")
            return False
