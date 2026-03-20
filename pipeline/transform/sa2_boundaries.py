"""
SA2 boundary transformer.

1. Reads the SA2 2025 seed GeoJSON
2. Annotates each SA2 with its health region (via TA→DHB→region mapping)
3. Simplifies to TopoJSON for Observable choropleth
4. Extracts centroids and aggregates NZDep2018 from SA1→SA2, loading into
   fact_sa2_nzdep for the access analysis

Requires mapshaper (npm install -g mapshaper).
"""
import json
import subprocess
import shutil
import math
from pathlib import Path
import pandas as pd
from pipeline.transform.base import BaseTransformer
from pipeline.transform.dhb_regions import DHB_TO_REGION

SA2_TOPOJSON_DEST = Path(__file__).parent.parent.parent / "src" / "data" / "nz-sa2.json"

# SA2 centroids output (JSON for Observable)
SA2_CENTROIDS_DEST = Path(__file__).parent.parent.parent / "src" / "data" / "sa2-centroids.json"


class SA2BoundariesTransformer(BaseTransformer):
    source_key = "sa2_boundaries"

    def transform(self, path: Path, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would process SA2 boundaries → TopoJSON + NZDep")
            return

        if not shutil.which("mapshaper"):
            self.log("WARNING: mapshaper not found — skipping. "
                     "Install with: npm install -g mapshaper")
            return

        # Load SA2 GeoJSON
        self.log(f"Loading {path}")
        with open(path) as f:
            data = json.load(f)

        features = data["features"]
        self.log(f"Loaded {len(features)} SA2 features")

        # Try to load NZDep SA1 data to aggregate to SA2
        nzdep_by_sa2 = self._aggregate_nzdep_to_sa2(conn)

        # Compute centroids and annotate features
        centroids = []
        for feat in features:
            props = feat["properties"]
            if props is None:
                continue
            sa2_code = props.get("sa2_code", "")
            sa2_name = props.get("sa2_name", "")

            geom = feat.get("geometry")
            if geom is None:
                continue

            # Compute centroid from geometry
            centroid = self._compute_centroid(geom)

            # Get NZDep for this SA2
            nzdep = nzdep_by_sa2.get(sa2_code, {})

            centroids.append({
                "sa2_code": sa2_code,
                "sa2_name": sa2_name,
                "lat": centroid[1],
                "lon": centroid[0],
                "nzdep_quintile": nzdep.get("quintile"),
                "nzdep_score": nzdep.get("score"),
                "health_region": nzdep.get("health_region", ""),
            })

            # Annotate feature for choropleth
            props["nzdep_quintile"] = nzdep.get("quintile", 0)
            props["nzdep_score"] = round(nzdep.get("score", 0), 2) if nzdep.get("score") else 0
            props["health_region"] = nzdep.get("health_region", "")

        # Write annotated GeoJSON to temp file
        annotated = path.parent / "sa2-annotated.geojson"
        with open(annotated, "w") as f:
            json.dump(data, f)

        # Simplify and convert to TopoJSON
        SA2_TOPOJSON_DEST.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            "mapshaper", str(annotated),
            "-simplify", "20%", "keep-shapes",
            "-o", "format=topojson", str(SA2_TOPOJSON_DEST),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log(f"mapshaper failed: {result.stderr}")
            annotated.unlink(missing_ok=True)
            return

        size_kb = SA2_TOPOJSON_DEST.stat().st_size // 1024
        self.log(f"TopoJSON written to {SA2_TOPOJSON_DEST} ({size_kb} KB)")
        annotated.unlink(missing_ok=True)

        # Write centroids JSON for Observable
        with open(SA2_CENTROIDS_DEST, "w") as f:
            json.dump(centroids, f)
        self.log(f"Centroids written to {SA2_CENTROIDS_DEST} ({len(centroids)} SA2s)")

        # Load SA2 NZDep into DuckDB
        self._load_sa2_nzdep(conn, nzdep_by_sa2)

    def _aggregate_nzdep_to_sa2(self, conn):
        """Aggregate SA1 NZDep data to SA2 level using the raw Excel file."""
        try:
            nzdep_path = Path(__file__).parent.parent.parent / "data" / "raw" / "nzdep2018.xlsx"
            if not nzdep_path.exists():
                self.log("NZDep Excel not found — SA2 NZDep will be empty")
                return {}

            df = pd.read_excel(nzdep_path, sheet_name=0, engine="openpyxl")
            self.log(f"Loaded {len(df):,} SA1 rows for SA2 NZDep aggregation")

            # Normalise columns
            df["sa2_code"] = df["SA22018_code"].dropna().astype(int).astype(str)
            df["sa2_name"] = df["SA22018_name"].astype(str).str.strip()
            df["score"] = pd.to_numeric(df["NZDep2018_Score"], errors="coerce")
            df["quintile"] = pd.to_numeric(df["NZDep2018"], errors="coerce")
            df["dhb"] = df["DHB_2018_name"].astype(str).str.strip()
            df["health_region"] = df["dhb"].map(DHB_TO_REGION)

            result = {}
            for sa2_code, group in df.groupby("sa2_code"):
                scores = group["score"].dropna()
                deciles = group["quintile"].dropna()  # NZDep2018 is actually 1-10 decile
                regions = group["health_region"].dropna()

                if scores.empty:
                    continue

                # Convert decile to quintile: 1-2→Q1, 3-4→Q2, 5-6→Q3, 7-8→Q4, 9-10→Q5
                modal_decile = int(deciles.mode().iloc[0]) if not deciles.empty else None
                quintile = math.ceil(modal_decile / 2) if modal_decile else None
                region = regions.mode().iloc[0] if not regions.empty else ""

                result[sa2_code] = {
                    "score": float(scores.mean()),
                    "quintile": quintile,
                    "sa1_count": len(scores),
                    "sa2_name": group["sa2_name"].iloc[0],
                    "health_region": region,
                }

            self.log(f"Aggregated NZDep to {len(result)} SA2 areas")
            return result

        except Exception as e:
            self.log(f"NZDep aggregation failed: {e}")
            return {}

    def _load_sa2_nzdep(self, conn, nzdep_by_sa2):
        """Load SA2-level NZDep into DuckDB."""
        conn.execute("DELETE FROM fact_sa2_nzdep")

        inserted = 0
        for sa2_code, data in nzdep_by_sa2.items():
            conn.execute("""
                INSERT INTO fact_sa2_nzdep
                    (id, sa2_code, sa2_name, nzdep_mean_score, nzdep_quintile,
                     sa1_count, health_region, source)
                VALUES (nextval('fact_sa2_nzdep_id_seq'), ?, ?, ?, ?, ?, ?, ?)
            """, (
                sa2_code,
                data.get("sa2_name", ""),
                data.get("score"),
                data.get("quintile"),
                data.get("sa1_count", 0),
                data.get("health_region", ""),
                "NZDep2018 SA1→SA2 aggregation",
            ))
            inserted += 1

        self.log(f"Done: {inserted} SA2 NZDep rows inserted")

    @staticmethod
    def _compute_centroid(geometry):
        """Compute a simple centroid from a GeoJSON geometry (lon, lat)."""
        coords = []

        def extract_coords(geom):
            gtype = geom.get("type", "")
            if gtype == "Polygon":
                # Use exterior ring only
                for lon, lat, *_ in geom["coordinates"][0]:
                    coords.append((lon, lat))
            elif gtype == "MultiPolygon":
                for polygon in geom["coordinates"]:
                    for lon, lat, *_ in polygon[0]:
                        coords.append((lon, lat))

        extract_coords(geometry)
        if not coords:
            return (0, 0)

        avg_lon = sum(c[0] for c in coords) / len(coords)
        avg_lat = sum(c[1] for c in coords) / len(coords)
        return (round(avg_lon, 6), round(avg_lat, 6))
