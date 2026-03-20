"""
SA2 2025 boundary fetcher.

Returns the pre-simplified seed GeoJSON from data/lookups/.
The original shapefile was downloaded from Stats NZ Datafinder (layer 120978),
reprojected to WGS84, and simplified to 0.5% with mapshaper.

Source: https://datafinder.stats.govt.nz/layer/120978-statistical-area-2-2025/
License: CC BY 4.0 (Stats NZ)
"""
from pathlib import Path
from pipeline.config import LOOKUP_DIR
from pipeline.fetch.base import BaseFetcher


class SA2BoundariesFetcher(BaseFetcher):
    source_key = "sa2_boundaries"

    def fetch(self, dry_run=False) -> Path:
        dest = LOOKUP_DIR / "sa2_2025_simplified.geojson"

        if dry_run:
            self.log(f"DRY RUN: would use SA2 seed GeoJSON at {dest}")
            return dest

        if not dest.exists():
            raise FileNotFoundError(
                f"SA2 seed GeoJSON not found at {dest}. "
                "Download from Stats NZ Datafinder and simplify with mapshaper."
            )

        size_mb = dest.stat().st_size / 1024 / 1024
        self.log(f"Using SA2 seed GeoJSON: {dest} ({size_mb:.1f} MB, 2,395 SA2 polygons)")
        return dest
