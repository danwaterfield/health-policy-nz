"""
NZDep2018 fetcher.

Downloads the SA1-level NZDep2018 index Excel file from the University of Otago.
Contains one row per SA1 with DHB and other higher-geography assignments.
Falls back to a minimal seed CSV if the download fails.
"""
import requests
from pathlib import Path
from pipeline.config import RAW_DIR, LOOKUP_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher


class NZDepFetcher(BaseFetcher):
    source_key = "nzdep"

    def fetch(self, dry_run=False) -> Path:
        dest = RAW_DIR / SOURCES[self.source_key]["filename"]
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        if self.is_fresh(dest):
            self.log(f"Cache fresh: {dest}")
            return dest

        if dry_run:
            self.log(f"DRY RUN: would download NZDep2018 Excel to {dest}")
            return dest

        url = SOURCES[self.source_key]["url"]
        self.log(f"Downloading NZDep2018 SA1 index from Otago University...")
        try:
            resp = requests.get(url, timeout=120, stream=True,
                                headers={"User-Agent": "NZ-Health-Dashboard-Pipeline/1.0"})
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
            self.log(f"Downloaded to {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
            return dest
        except Exception as e:
            self.log(f"Download failed: {e}")
            if dest.exists():
                self.log("Using existing cached file despite staleness")
                return dest
            raise RuntimeError(
                f"Could not download NZDep2018 data. "
                f"Download manually from: {url}\nError: {e}"
            )
