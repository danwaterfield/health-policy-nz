"""
NZ health facilities fetcher.

Queries OpenStreetMap Overpass API for GPs, hospitals, and urgent care
facilities in New Zealand. Falls back to a seed JSON file if the API
is unavailable.

Source: OpenStreetMap via Overpass API
License: ODbL (Open Database License)
"""
import json
import requests
from pathlib import Path
from pipeline.config import RAW_DIR, LOOKUP_DIR
from pipeline.fetch.base import BaseFetcher

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OVERPASS_QUERY = """
[out:json][timeout:120];
area["ISO3166-1"="NZ"]->.nz;
(
  nwr["amenity"="doctors"](area.nz);
  nwr["amenity"="hospital"](area.nz);
  nwr["amenity"="clinic"](area.nz);
  nwr["healthcare"="doctor"](area.nz);
  nwr["healthcare"="hospital"](area.nz);
  nwr["healthcare"="urgent_care"](area.nz);
);
out center body;
"""


class FacilitiesFetcher(BaseFetcher):
    source_key = "facilities"

    def fetch(self, dry_run=False) -> Path:
        dest = RAW_DIR / "nz_facilities.json"
        seed = LOOKUP_DIR / "facilities_seed.json"
        RAW_DIR.mkdir(parents=True, exist_ok=True)

        if self.is_fresh(dest):
            self.log(f"Cache fresh: {dest}")
            return dest

        if dry_run:
            self.log(f"DRY RUN: would query Overpass API for NZ health facilities")
            return seed if seed.exists() else dest

        self.log("Querying Overpass API for NZ health facilities...")
        try:
            resp = requests.post(
                OVERPASS_URL,
                data={"data": OVERPASS_QUERY},
                timeout=180,
                headers={"User-Agent": "NZ-Health-Dashboard-Pipeline/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()

            elements = data.get("elements", [])
            self.log(f"Received {len(elements)} raw elements from Overpass")

            # Normalise to a clean facility list
            facilities = []
            for el in elements:
                tags = el.get("tags", {})
                lat = el.get("lat") or el.get("center", {}).get("lat")
                lon = el.get("lon") or el.get("center", {}).get("lon")

                if lat is None or lon is None:
                    continue

                facility_type = self._classify(tags)
                if facility_type is None:
                    continue

                facilities.append({
                    "name": tags.get("name", "Unknown"),
                    "facility_type": facility_type,
                    "latitude": lat,
                    "longitude": lon,
                    "osm_id": el.get("id"),
                    "source": "osm",
                })

            # Deduplicate by OSM ID
            seen = set()
            deduped = []
            for f in facilities:
                if f["osm_id"] not in seen:
                    seen.add(f["osm_id"])
                    deduped.append(f)

            with open(dest, "w") as f:
                json.dump(deduped, f, indent=2)

            self.log(f"Saved {len(deduped)} facilities to {dest}")

            # Also save as seed for offline use
            LOOKUP_DIR.mkdir(parents=True, exist_ok=True)
            with open(seed, "w") as f:
                json.dump(deduped, f, indent=2)
            self.log(f"Updated seed file: {seed}")

            return dest

        except Exception as e:
            self.log(f"Overpass query failed: {e}")
            if dest.exists():
                self.log("Using existing cached file")
                return dest
            if seed.exists():
                self.log(f"Falling back to seed file: {seed}")
                return seed
            raise RuntimeError(f"Cannot fetch facilities: {e}")

    @staticmethod
    def _classify(tags):
        """Classify OSM tags into facility_type."""
        amenity = tags.get("amenity", "")
        healthcare = tags.get("healthcare", "")

        if healthcare == "urgent_care":
            return "urgent_care"
        if amenity == "hospital" or healthcare == "hospital":
            return "hospital"
        if amenity in ("doctors", "clinic") or healthcare == "doctor":
            return "gp"
        return None
