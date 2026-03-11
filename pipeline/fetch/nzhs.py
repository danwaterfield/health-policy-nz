"""
NZ Health Survey fetcher.

The NZHS prevalence CSV is available as a static file directly from the Shiny app
server — no Playwright required. Falls back to Playwright if the direct URL fails,
then to any existing local file, then raises.
"""
import requests
from pathlib import Path
from pipeline.config import RAW_DIR, SOURCES, LOOKUP_DIR
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

        # 1. Try direct HTTP download (fast, no browser required)
        if self._http_download(dest):
            self.strip_bom(dest)
            self.log(f"Downloaded via HTTP to {dest}")
            return dest

        # 2. Try Playwright as fallback
        self.log("HTTP download failed; attempting Playwright fallback...")
        if self._playwright_download(dest):
            self.strip_bom(dest)
            self.log(f"Downloaded via Playwright to {dest}")
            return dest

        # 3. Use existing local file if present
        if dest.exists():
            self.log("Using existing local file")
            return dest

        # 4. Use committed seed file if present
        seed = LOOKUP_DIR / "nzhs_prevalence_seed.csv"
        if seed.exists():
            self.log(f"Using seed file: {seed}")
            import shutil
            shutil.copy(seed, dest)
            return dest

        url = SOURCES[self.source_key]["url"]
        raise RuntimeError(
            "NZHS download failed. Manually download the prevalence CSV from "
            f"{url} and save to {dest}"
        )

    def _http_download(self, dest: Path) -> bool:
        url = SOURCES[self.source_key]["url"]
        try:
            self.log(f"Downloading {url}")
            r = requests.get(url, timeout=120, stream=True)
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            return True
        except Exception as e:
            self.log(f"HTTP download failed: {e}")
            return False

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
