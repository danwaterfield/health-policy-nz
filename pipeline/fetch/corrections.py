"""
Corrections NZ prison population fetcher.

Uses a manually maintained seed CSV derived from Corrections NZ quarterly
prison statistics. The quarterly Excel files are linked from JS-rendered pages
and change URL each quarter; seed approach is more reliable.

Source: https://www.corrections.govt.nz/resources/statistics/quarterly_prison_statistics
"""
from pathlib import Path
from pipeline.config import LOOKUP_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher


class CorrectionsFetcher(BaseFetcher):
    source_key = "corrections"

    def fetch(self, dry_run=False) -> Path:
        seed = LOOKUP_DIR / SOURCES[self.source_key]["filename"]
        if not seed.exists():
            raise FileNotFoundError(
                f"Corrections seed CSV not found at {seed}. "
                f"Populate from Corrections NZ quarterly prison statistics."
            )
        if dry_run:
            self.log(f"DRY RUN: would use seed {seed}")
            return seed
        self.log(f"Using seed CSV: {seed}")
        return seed
