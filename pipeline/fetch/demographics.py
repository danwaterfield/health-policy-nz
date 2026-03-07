"""
Stats NZ subnational population projections fetcher.

Attempts direct Excel download from Stats NZ. Falls back to seed data if unavailable.
"""
import requests
from pathlib import Path
from pipeline.config import RAW_DIR, LOOKUP_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher

# Known direct download URL for the 2023-based projections Excel file
EXCEL_DIRECT_URL = (
    "https://www.stats.govt.nz/assets/Uploads/Subnational-population-projections/"
    "Subnational-population-projections-2023base-2048-update/Download-data/"
    "subnational-pop-projections-2023base-2048.xlsx"
)


class DemographicsFetcher(BaseFetcher):
    source_key = "demographics"

    def fetch(self, dry_run=False) -> Path:
        dest = RAW_DIR / SOURCES[self.source_key]["filename"]
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        if self.is_fresh(dest):
            self.log(f"Cache fresh: {dest}")
            return dest

        if dry_run:
            self.log(f"DRY RUN: would download Stats NZ projections Excel to {dest}")
            return dest

        self.log(f"Downloading Stats NZ population projections...")
        try:
            resp = requests.get(EXCEL_DIRECT_URL, timeout=120, stream=True)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
            self.log(f"Downloaded to {dest} ({dest.stat().st_size / 1024:.0f} KB)")
            return dest
        except Exception as e:
            self.log(f"Direct download failed: {e}")
            seed = LOOKUP_DIR / "demographics_seed.csv"
            if seed.exists():
                self.log(f"Falling back to seed CSV: {seed}")
                return seed
            if dest.exists():
                self.log("Using existing cached file despite staleness")
                return dest
            raise RuntimeError(
                f"Could not download demographics data and no fallback available. Error: {e}"
            )
