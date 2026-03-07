"""
Census age distribution fetcher.

Uses a manually maintained seed CSV derived from Stats NZ 2018 Census
QuickStats on culture and identity. Age distributions by ethnicity are
stable between censuses and used for age-composition bias annotation.

Source: https://www.stats.govt.nz/2018-census/
"""
from pathlib import Path
from pipeline.config import LOOKUP_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher


class CensusAgeFetcher(BaseFetcher):
    source_key = "census_age"

    def fetch(self, dry_run=False) -> Path:
        seed = LOOKUP_DIR / SOURCES[self.source_key]["filename"]
        if not seed.exists():
            raise FileNotFoundError(
                f"Census age seed CSV not found at {seed}."
            )
        if dry_run:
            self.log(f"DRY RUN: would use seed {seed}")
            return seed
        self.log(f"Using seed CSV: {seed}")
        return seed
