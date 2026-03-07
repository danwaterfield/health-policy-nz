"""
Electoral Commission Māori roll fetcher.

Uses a manually maintained seed CSV derived from Electoral Commission
enrolment statistics. Direct Excel download requires navigating JS-rendered
pages; a seed CSV is the practical approach until automated scraping is added.

Source: https://elections.nz/stats-and-research/enrolment-statistics/enrolment-by-general-electorate/maori-enrolment/
"""
from pathlib import Path
from pipeline.config import LOOKUP_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher


class ElectoralFetcher(BaseFetcher):
    source_key = "electoral"

    def fetch(self, dry_run=False) -> Path:
        seed = LOOKUP_DIR / SOURCES[self.source_key]["filename"]
        if not seed.exists():
            raise FileNotFoundError(
                f"Electoral seed CSV not found at {seed}. "
                f"Populate from Electoral Commission enrolment statistics."
            )
        if dry_run:
            self.log(f"DRY RUN: would use seed {seed}")
            return seed
        self.log(f"Using seed CSV: {seed}")
        return seed
