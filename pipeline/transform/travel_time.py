"""
Travel time transformer.

For each SA2 centroid, estimates travel time to nearest GP, hospital,
and urgent care facility.

Two modes:
1. Fast (default): Haversine distance × winding factor → estimated drive time.
   Completes in seconds for all SA2s. Good enough for PoC visualisation.
2. OSRM: Actual routing via public OSRM API. Set OSRM_ROUTING=1 env var.
   Much slower (~70 min) but gives real road distances.

Results are cached as a seed CSV so future runs load instantly.
"""
import json
import math
import os
import time
import csv
import requests
from pathlib import Path
from pipeline.transform.base import BaseTransformer

OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving"
SA2_CENTROIDS = Path(__file__).parent.parent.parent / "src" / "data" / "sa2-centroids.json"
SEED_CSV = Path(__file__).parent.parent.parent / "data" / "lookups" / "travel_time_seed.csv"

# Haversine-to-drive-time conversion factors
# NZ average winding factor: ~1.4 (road distance / straight-line distance)
# Average speed: 60 km/h for rural, 35 km/h for urban
WINDING_FACTOR = 1.4
RURAL_SPEED_KMH = 55
URBAN_SPEED_KMH = 35
URBAN_DISTANCE_THRESHOLD_KM = 5
# Cap estimated travel time (Chatham Islands etc. have no road connection)
MAX_TRAVEL_MINUTES = 180


class TravelTimeTransformer(BaseTransformer):
    source_key = "travel_time"

    def transform(self, conn, dry_run=False):
        """Derived transformer — no raw_path, runs after facilities."""
        if dry_run:
            self.log("DRY RUN: would compute travel times")
            return

        conn.execute("DELETE FROM fact_access")

        # Check for seed CSV first
        if SEED_CSV.exists():
            self.log(f"Loading travel times from seed: {SEED_CSV}")
            self._load_seed(conn)
            return

        centroids = self._load_centroids()
        if not centroids:
            self.log("No SA2 centroids found — skipping")
            return

        facilities = self._load_facilities(conn)
        if not facilities:
            self.log("No facilities in DB — skipping")
            return

        use_osrm = os.getenv("OSRM_ROUTING", "0") == "1"
        mode = "OSRM" if use_osrm else "Haversine estimate"
        self.log(f"Computing travel times ({mode}) for {len(centroids)} SA2s "
                 f"to {len(facilities)} facilities...")

        # Pre-group facilities by type
        fac_by_type = {}
        for f in facilities:
            fac_by_type.setdefault(f["type"], []).append(f)

        results = []
        for i, sa2 in enumerate(centroids):
            if sa2["lat"] == 0 and sa2["lon"] == 0:
                continue

            for ftype in ["gp", "hospital", "urgent_care"]:
                type_facilities = fac_by_type.get(ftype, [])
                if not type_facilities:
                    continue

                # Find nearest facilities by Haversine
                nearest = self._nearest_by_haversine(
                    sa2["lat"], sa2["lon"], type_facilities, 5
                )

                if use_osrm:
                    best_minutes, best_km, count_30 = self._route_osrm(
                        sa2["lat"], sa2["lon"], nearest
                    )
                else:
                    best_minutes, best_km, count_30 = self._estimate_haversine(
                        sa2["lat"], sa2["lon"], nearest
                    )

                # Cap unreachable locations (islands, extreme remote)
                if best_minutes is not None and best_minutes > MAX_TRAVEL_MINUTES:
                    best_minutes = MAX_TRAVEL_MINUTES

                if best_minutes is not None:
                    results.append({
                        "sa2_code": sa2["sa2_code"],
                        "sa2_name": sa2["sa2_name"],
                        "facility_type": ftype,
                        "nearest_minutes": round(best_minutes, 1),
                        "nearest_km": round(best_km, 1),
                        "facility_count_30min": count_30,
                        "nzdep_quintile": sa2.get("nzdep_quintile"),
                        "nzdep_score": sa2.get("nzdep_score"),
                        "health_region": sa2.get("health_region", ""),
                        "centroid_lat": sa2["lat"],
                        "centroid_lon": sa2["lon"],
                    })

            if (i + 1) % 500 == 0:
                self.log(f"  Progress: {i + 1}/{len(centroids)} SA2s")

        # Insert into DuckDB
        inserted = 0
        for r in results:
            conn.execute("""
                INSERT INTO fact_access
                    (id, sa2_code, sa2_name, facility_type,
                     nearest_minutes, nearest_km, facility_count_30min,
                     nzdep_quintile, nzdep_score, health_region,
                     centroid_lat, centroid_lon, source)
                VALUES (nextval('fact_access_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r["sa2_code"], r["sa2_name"], r["facility_type"],
                r["nearest_minutes"], r["nearest_km"], r["facility_count_30min"],
                r["nzdep_quintile"], r["nzdep_score"], r["health_region"],
                r["centroid_lat"], r["centroid_lon"],
                f"{mode}",
            ))
            inserted += 1

        self.log(f"Done: {inserted} access rows inserted ({mode})")
        self._save_seed(results)

    def _estimate_haversine(self, lat, lon, candidates):
        """Estimate drive time from Haversine distance with winding factor."""
        best_minutes = None
        best_km = None
        count_30 = 0

        for fac in candidates:
            straight_km = self._haversine_km(lat, lon, fac["lat"], fac["lon"])
            road_km = straight_km * WINDING_FACTOR

            # Speed depends on distance (proxy for urban/rural)
            speed = URBAN_SPEED_KMH if straight_km < URBAN_DISTANCE_THRESHOLD_KM else RURAL_SPEED_KMH
            minutes = (road_km / speed) * 60

            if best_minutes is None or minutes < best_minutes:
                best_minutes = minutes
                best_km = road_km
            if minutes <= 30:
                count_30 += 1

        return best_minutes, best_km, count_30

    def _route_osrm(self, lat, lon, candidates):
        """Route to candidates via OSRM API."""
        best_minutes = None
        best_km = None
        count_30 = 0

        for fac in candidates:
            try:
                url = f"{OSRM_ROUTE_URL}/{lon},{lat};{fac['lon']},{fac['lat']}?overview=false"
                resp = requests.get(url, timeout=15)
                time.sleep(0.3)

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("code") == "Ok":
                        route = data["routes"][0]
                        minutes = route["duration"] / 60
                        km = route["distance"] / 1000
                        if best_minutes is None or minutes < best_minutes:
                            best_minutes = minutes
                            best_km = km
                        if minutes <= 30:
                            count_30 += 1
            except Exception:
                continue

        return best_minutes, best_km, count_30

    def _load_centroids(self):
        if not SA2_CENTROIDS.exists():
            return []
        with open(SA2_CENTROIDS) as f:
            return json.load(f)

    def _load_facilities(self, conn):
        rows = conn.execute(
            "SELECT facility_type, latitude, longitude FROM fact_facilities"
        ).fetchall()
        return [{"type": r[0], "lat": r[1], "lon": r[2]} for r in rows]

    @staticmethod
    def _haversine_km(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def _nearest_by_haversine(self, lat, lon, facilities, n):
        with_dist = []
        for f in facilities:
            d = self._haversine_km(lat, lon, f["lat"], f["lon"])
            with_dist.append((d, f))
        with_dist.sort(key=lambda x: x[0])
        return [f for _, f in with_dist[:n]]

    def _load_seed(self, conn):
        """Load pre-computed travel times from seed CSV."""
        inserted = 0
        with open(SEED_CSV) as f:
            reader = csv.DictReader(f)
            for row in reader:
                nearest_min = row.get("nearest_minutes")
                if not nearest_min or nearest_min == "":
                    continue
                conn.execute("""
                    INSERT INTO fact_access
                        (id, sa2_code, sa2_name, facility_type,
                         nearest_minutes, nearest_km, facility_count_30min,
                         nzdep_quintile, nzdep_score, health_region,
                         centroid_lat, centroid_lon, source)
                    VALUES (nextval('fact_access_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    row["sa2_code"], row.get("sa2_name", ""), row["facility_type"],
                    float(nearest_min),
                    float(row["nearest_km"]) if row.get("nearest_km") else None,
                    int(row["facility_count_30min"]) if row.get("facility_count_30min") else 0,
                    int(row["nzdep_quintile"]) if row.get("nzdep_quintile") and row["nzdep_quintile"] != "" else None,
                    float(row["nzdep_score"]) if row.get("nzdep_score") and row["nzdep_score"] != "" else None,
                    row.get("health_region", ""),
                    float(row["centroid_lat"]) if row.get("centroid_lat") else None,
                    float(row["centroid_lon"]) if row.get("centroid_lon") else None,
                    "OSRM public API (cached)",
                ))
                inserted += 1
        self.log(f"Done: {inserted} access rows loaded from seed")

    def _save_seed(self, results):
        """Save computed results as seed CSV for future runs."""
        SEED_CSV.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = [
            "sa2_code", "sa2_name", "facility_type",
            "nearest_minutes", "nearest_km", "facility_count_30min",
            "nzdep_quintile", "nzdep_score", "health_region",
            "centroid_lat", "centroid_lon",
        ]
        with open(SEED_CSV, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in results:
                writer.writerow({k: r.get(k, "") for k in fieldnames})
        self.log(f"Seed saved: {SEED_CSV} ({len(results)} rows)")
