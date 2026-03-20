// src/components/access-detail.js
/**
 * Popup content builders for SA2 and facility click-to-detail.
 * Returns HTML strings for Leaflet popups.
 * No Observable globals — pure functions only.
 */
import {haversineKm} from "./access-stats.js";

const WINDING_FACTOR = 1.4;
const URBAN_SPEED = 35;
const RURAL_SPEED = 55;
const URBAN_THRESHOLD_KM = 5;

function estimateMinutes(km) {
  const road = km * WINDING_FACTOR;
  const speed = km < URBAN_THRESHOLD_KM ? URBAN_SPEED : RURAL_SPEED;
  return (road / speed) * 60;
}

/**
 * Find nearest facility of a given type to a point.
 * @returns {{name, lat, lon, distance_km, minutes}} or null
 */
export function findNearestFacility(lat, lon, facilities, type) {
  let best = null;
  let bestDist = Infinity;
  for (const f of facilities) {
    if (type && f.facility_type !== type) continue;
    if (f.latitude == null || f.longitude == null) continue;
    const d = haversineKm(lat, lon, f.latitude, f.longitude);
    if (d < bestDist) {
      bestDist = d;
      best = f;
    }
  }
  if (!best) return null;
  return {
    name: best.name,
    lat: best.latitude,
    lon: best.longitude,
    distance_km: Math.round(bestDist * 10) / 10,
    minutes: Math.round(estimateMinutes(bestDist)),
  };
}

/**
 * Build popup HTML for an SA2 area click.
 */
export function buildSA2Popup(sa2Code, accessLookup, nzdepLookup, facilities, centroids, nationalMedianGP) {
  const nz = nzdepLookup.get(sa2Code);
  const access = accessLookup.get(sa2Code);
  const centroid = centroids.find(c => c.sa2_code === sa2Code);

  const name = nz?.sa2_name || centroid?.sa2_name || sa2Code;
  const lines = [];
  lines.push(`<strong style="font-size:1.1em;">${esc(name)}</strong>`);

  if (nz) {
    lines.push(`NZDep: <strong>Q${nz.nzdep_quintile}</strong> (score: ${nz.nzdep_mean_score?.toFixed(1) ?? "—"})` +
      (nz.population ? ` &middot; Pop: ${nz.population.toLocaleString()}` : ""));
  } else {
    lines.push(`<span style="color:#999;">No NZDep data (SA2 2025/2018 mismatch)</span>`);
  }

  if (centroid && facilities.length > 0) {
    const nearGP = findNearestFacility(centroid.lat, centroid.lon, facilities, "gp");
    const nearHosp = findNearestFacility(centroid.lat, centroid.lon, facilities, "hospital");

    if (nearGP) {
      lines.push(`<br><strong>Nearest GP:</strong> ${esc(nearGP.name)}`);
      lines.push(`&nbsp;&nbsp;${nearGP.distance_km} km &middot; ~${nearGP.minutes} min drive`);
    }
    if (nearHosp) {
      lines.push(`<strong>Nearest hospital:</strong> ${esc(nearHosp.name)}`);
      lines.push(`&nbsp;&nbsp;${nearHosp.distance_km} km &middot; ~${nearHosp.minutes} min drive`);
    }
  }

  if (access && nationalMedianGP > 0) {
    const ratio = access.nearest_minutes / nationalMedianGP;
    if (ratio > 1.5) {
      lines.push(`<br><span style="color:#d73027;"><strong>${ratio.toFixed(1)}x</strong> the national median drive time</span>`);
    } else if (ratio < 0.5) {
      lines.push(`<br><span style="color:#1a9850;"><strong>${ratio.toFixed(1)}x</strong> the national median</span>`);
    }
  }

  if (access) {
    lines.push(`<span style="color:#666; font-size:0.85em;">Facilities within 30 min: ${access.facility_count_30min ?? "—"}</span>`);
  }

  return `<div style="font-size:12px; line-height:1.5; max-width:260px;">${lines.join("<br>")}</div>`;
}

/**
 * Build popup HTML for a facility marker click.
 */
export function buildFacilityPopup(facility, nzdepLookup, centroids) {
  const lines = [];
  lines.push(`<strong style="font-size:1.1em;">${esc(facility.name)}</strong>`);
  lines.push(`Type: <strong>${facility.facility_type === "gp" ? "GP / Clinic" : "Hospital"}</strong>`);

  if (facility.sa2_name) {
    const nz = [...nzdepLookup.values()].find(d => d.sa2_name === facility.sa2_name);
    lines.push(`SA2: ${esc(facility.sa2_name)}${nz ? ` (NZDep Q${nz.nzdep_quintile})` : ""}`);
  }

  // Count SA2s for which this is the nearest facility
  if (centroids.length > 0 && facility.latitude != null) {
    let count = 0;
    for (const c of centroids) {
      if (c.lat === 0 && c.lon === 0) continue;
      const d = (facility.latitude - c.lat) ** 2 + (facility.longitude - c.lon) ** 2;
      // Quick check: is this the closest facility of its type?
      // (approximate — uses squared Euclidean, good enough for counting)
      count++; // Placeholder — full computation too expensive for popup
    }
    // Skip count for now — would need full facility scan per centroid
  }

  if (facility.health_region) {
    lines.push(`Region: ${esc(facility.health_region)}`);
  }

  return `<div style="font-size:12px; line-height:1.5; max-width:240px;">${lines.join("<br>")}</div>`;
}

/** Escape HTML entities to prevent XSS in popup content. */
function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
