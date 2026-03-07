"""
NZ DHB boundary fetcher.

Downloads the generalised NZ District Health Board boundaries from ArcGIS
Open Data (eaglegis layer, hosted via Pacific GIS portal).

The resulting file is processed by BoundariesTransformer into a simplified
TopoJSON at src/data/nz-health-regions.json.

Source: https://www.arcgis.com/home/item.html?id=bab0ff4386eb4522b87d9cda6883f178
"""
import requests
from pathlib import Path
from pipeline.config import RAW_DIR, SOURCES
from pipeline.fetch.base import BaseFetcher

GEOJSON_URL = (
    "https://opendata.arcgis.com/api/v3/datasets/"
    "bab0ff4386eb4522b87d9cda6883f178_0/downloads/data"
    "?format=geojson&spatialRefId=4326"
)


class BoundariesFetcher(BaseFetcher):
    source_key = "boundaries"

    def fetch(self, dry_run=False) -> Path:
        dest = RAW_DIR / "nz-dhb.geojson"
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        if self.is_fresh(dest):
            self.log(f"Cache fresh: {dest}")
            return dest

        if dry_run:
            self.log(f"DRY RUN: would download DHB boundaries GeoJSON to {dest}")
            return dest

        self.log("Downloading NZ DHB generalised boundaries from ArcGIS Open Data...")
        try:
            resp = requests.get(
                GEOJSON_URL, timeout=120, stream=True,
                headers={"User-Agent": "NZ-Health-Dashboard-Pipeline/1.0"},
            )
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
            raise RuntimeError(f"Cannot download DHB boundaries: {e}")
