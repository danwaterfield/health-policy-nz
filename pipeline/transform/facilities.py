"""
Health facilities transformer.

Loads facility JSON (from OSM Overpass or seed), assigns each facility
to an SA2 by nearest-centroid lookup, and inserts into fact_facilities.
"""
import json
import math
from pathlib import Path
from pipeline.transform.base import BaseTransformer

SA2_CENTROIDS = Path(__file__).parent.parent.parent / "src" / "data" / "sa2-centroids.json"


class FacilitiesTransformer(BaseTransformer):
    source_key = "facilities"

    def transform(self, path: Path, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would load facilities into fact_facilities")
            return

        conn.execute("DELETE FROM fact_facilities")

        with open(path) as f:
            facilities = json.load(f)

        self.log(f"Loaded {len(facilities)} facilities from {path}")

        # Load SA2 centroids for assignment
        sa2_lookup = self._load_sa2_centroids()

        inserted = 0
        for fac in facilities:
            lat = fac.get("latitude")
            lon = fac.get("longitude")
            if lat is None or lon is None:
                continue

            # Find nearest SA2 by centroid distance
            sa2 = self._find_nearest_sa2(lat, lon, sa2_lookup)

            conn.execute("""
                INSERT INTO fact_facilities
                    (id, name, facility_type, latitude, longitude,
                     sa2_code, sa2_name, health_region, source)
                VALUES (nextval('fact_facilities_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                fac.get("name", "Unknown"),
                fac.get("facility_type"),
                lat, lon,
                sa2.get("sa2_code", "") if sa2 else "",
                sa2.get("sa2_name", "") if sa2 else "",
                sa2.get("health_region", "") if sa2 else "",
                fac.get("source", "osm"),
            ))
            inserted += 1

        self.log(f"Done: {inserted} facilities inserted")

    def _load_sa2_centroids(self):
        """Load SA2 centroids JSON."""
        if not SA2_CENTROIDS.exists():
            self.log("WARNING: SA2 centroids not found — facilities won't have SA2 assignment")
            return []

        with open(SA2_CENTROIDS) as f:
            return json.load(f)

    @staticmethod
    def _find_nearest_sa2(lat, lon, centroids):
        """Find the nearest SA2 centroid by Haversine distance."""
        if not centroids:
            return None

        best = None
        best_dist = float("inf")

        for c in centroids:
            clat = c.get("lat", 0)
            clon = c.get("lon", 0)
            if clat == 0 and clon == 0:
                continue

            # Simple squared-distance approximation (good enough at NZ latitudes)
            dlat = lat - clat
            dlon = (lon - clon) * math.cos(math.radians(lat))
            dist = dlat * dlat + dlon * dlon

            if dist < best_dist:
                best_dist = dist
                best = c

        return best
