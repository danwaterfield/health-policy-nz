"""
Stats NZ period life tables fetcher.

Downloads the 2017-19 national and subnational period life tables Excel
from Stats NZ. Contains Māori, non-Māori, Pacific, and total life tables
by age band and sex.
"""
import requests
from pathlib import Path
from pipeline.config import RAW_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher


class LifeTablesFetcher(BaseFetcher):
    source_key = "life_tables"

    def fetch(self, dry_run=False) -> Path:
        dest = RAW_DIR / SOURCES[self.source_key]["filename"]
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        if self.is_fresh(dest):
            self.log(f"Cache fresh: {dest}")
            return dest

        if dry_run:
            self.log(f"DRY RUN: would download Stats NZ life tables to {dest}")
            return dest

        url = SOURCES[self.source_key]["url"]
        self.log("Downloading Stats NZ period life tables 2017-19...")
        try:
            resp = requests.get(url, timeout=120, stream=True,
                                headers={"User-Agent": "NZ-Health-Dashboard-Pipeline/1.0"})
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            self.log(f"Downloaded to {dest} ({dest.stat().st_size / 1024:.0f} KB)")
            return dest
        except Exception as e:
            self.log(f"Download failed: {e}")
            if dest.exists():
                self.log("Using existing cached file despite staleness")
                return dest
            raise RuntimeError(
                f"Could not download life tables. "
                f"Download manually from: {url}\nError: {e}"
            )
