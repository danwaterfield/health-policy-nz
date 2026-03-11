"""
NZ DHB boundary transformer.

Reads the raw DHB GeoJSON, adds health_region property to each feature
using the same DHB→region mapping as the NZDep transformer, simplifies
to ~1% detail using mapshaper, and writes the result as TopoJSON to
src/data/nz-health-regions.json.

Requires mapshaper (npm install -g mapshaper).
"""
import json
import subprocess
import shutil
from pathlib import Path
from pipeline.transform.base import BaseTransformer
from pipeline.transform.dhb_regions import DHB_TO_REGION

TOPOJSON_DEST = Path(__file__).parent.parent.parent / "src" / "data" / "nz-health-regions.json"


class BoundariesTransformer(BaseTransformer):
    source_key = "boundaries"

    def transform(self, path: Path, conn=None, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would process DHB boundaries → TopoJSON")
            return

        # Check mapshaper is available
        if not shutil.which("mapshaper"):
            self.log("WARNING: mapshaper not found — skipping boundary processing. "
                     "Install with: npm install -g mapshaper")
            return

        # Load and annotate GeoJSON
        self.log(f"Loading {path}")
        with open(path) as f:
            data = json.load(f)

        unmatched = []
        for feature in data["features"]:
            dhb = feature["properties"].get("DHB_name", "")
            region = DHB_TO_REGION.get(dhb)
            if region is None:
                unmatched.append(dhb)
            feature["properties"]["health_region"] = region or "Unknown"
            feature["properties"]["name"] = dhb

        if unmatched:
            self.log(f"WARNING: unmatched DHBs: {unmatched}")

        # Write annotated GeoJSON to a temp file
        annotated = path.parent / "nz-dhb-annotated.geojson"
        with open(annotated, "w") as f:
            json.dump(data, f)

        # Simplify and convert to TopoJSON with mapshaper
        TOPOJSON_DEST.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "mapshaper", str(annotated),
            "-simplify", "1%", "keep-shapes",
            "-o", "format=topojson", str(TOPOJSON_DEST),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log(f"mapshaper failed: {result.stderr}")
            return

        size_kb = TOPOJSON_DEST.stat().st_size // 1024
        self.log(f"Done: TopoJSON written to {TOPOJSON_DEST} ({size_kb} KB)")
        annotated.unlink(missing_ok=True)
