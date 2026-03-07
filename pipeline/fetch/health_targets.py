"""Health NZ quarterly health targets fetcher — uses seed CSV."""
from pathlib import Path
from pipeline.config import LOOKUP_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher


class HealthTargetsFetcher(BaseFetcher):
    source_key = "health_targets"

    def fetch(self, dry_run=False) -> Path:
        seed = LOOKUP_DIR / SOURCES[self.source_key]["filename"]
        if not seed.exists():
            raise FileNotFoundError(
                f"Seed file not found: {seed}. "
                "This is a manually-maintained file — add it to data/lookups/."
            )
        if dry_run:
            self.log(f"DRY RUN: would use seed CSV {seed}")
        else:
            self.log(f"Using seed CSV: {seed}")
        return seed
