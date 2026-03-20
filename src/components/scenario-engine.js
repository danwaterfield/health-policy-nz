/**
 * What-if scenario engine for health access analysis.
 * Pure functions — no DOM, no Observable globals.
 */
import {haversineKm} from "./access-stats.js";

const WINDING = 1.4;
const URBAN_SPEED = 35;
const RURAL_SPEED = 55;
const URBAN_THRESHOLD = 5;
const MAX_MINUTES = 180;

function estimateMinutes(straightKm) {
  const roadKm = straightKm * WINDING;
  const speed = straightKm < URBAN_THRESHOLD ? URBAN_SPEED : RURAL_SPEED;
  return Math.min((roadKm / speed) * 60, MAX_MINUTES);
}

/**
 * Find nearest facility to a point from a list.
 * @returns {{index, name, minutes, km}} or null
 */
export function findNearest(lat, lon, facilityList, type) {
  let bestIdx = -1, bestDist = Infinity;
  for (let i = 0; i < facilityList.length; i++) {
    const f = facilityList[i];
    if (type && f.facility_type !== type) continue;
    if (f.latitude == null) continue;
    const d = haversineKm(lat, lon, f.latitude, f.longitude);
    if (d < bestDist) { bestDist = d; bestIdx = i; }
  }
  if (bestIdx < 0) return null;
  return {
    index: bestIdx,
    name: facilityList[bestIdx].name,
    minutes: estimateMinutes(bestDist),
    km: Math.round(bestDist * WINDING * 10) / 10,
  };
}

/**
 * Remove a facility and recompute affected SA2s.
 * Returns a new accessData array with updated rows.
 */
export function removeFacility(facilityToRemove, allFacilities, accessData, centroids) {
  const remaining = allFacilities.filter(f => f !== facilityToRemove);
  return recomputeAccess(remaining, accessData, centroids);
}

/**
 * Remove facilities by percentage (pandemic mode). Seeded random.
 * Removes facilities serving the fewest SA2s first for determinism.
 */
export function removeFacilitiesByPercent(allFacilities, accessData, centroids, pct) {
  if (pct <= 0) return accessData;
  const count = Math.floor(allFacilities.length * pct / 100);
  // Sort by name for determinism (pseudo-random by removing alphabetically last)
  const sorted = [...allFacilities].sort((a, b) => (a.name || "").localeCompare(b.name || ""));
  const remaining = sorted.slice(0, sorted.length - count);
  return recomputeAccess(remaining, accessData, centroids);
}

/**
 * Apply fuel price multiplier to travel times.
 * @param {string} region - if set, only apply to that region; null = national
 */
export function applyFuelMultiplier(accessData, multiplier, region) {
  if (multiplier === 1) return accessData;
  return accessData.map(row => {
    if (region && row.health_region !== region) return row;
    return {
      ...row,
      nearest_minutes: Math.min(row.nearest_minutes * multiplier, MAX_MINUTES),
      nearest_km: row.nearest_km, // distance doesn't change, time does
    };
  });
}

/**
 * Apply telehealth cap — caps effective travel time.
 * @param {string} region - if set, only apply to that region; null = national
 */
export function applyTelehealthCap(accessData, capMinutes, region) {
  return accessData.map(row => {
    if (region && row.health_region !== region) return row;
    return {
      ...row,
      nearest_minutes: Math.min(row.nearest_minutes, capMinutes),
    };
  });
}

/**
 * Recompute access for all SA2s given a modified facility list.
 */
function recomputeAccess(facilityList, accessData, centroids) {
  const centroidMap = new Map(centroids.map(c => [c.sa2_code, c]));
  return accessData.map(row => {
    const c = centroidMap.get(row.sa2_code);
    if (!c || (c.lat === 0 && c.lon === 0)) return row;
    const nearest = findNearest(c.lat, c.lon, facilityList, row.facility_type);
    if (!nearest) return row;
    // Count facilities within 30 min
    let count30 = 0;
    for (const f of facilityList) {
      if (f.facility_type !== row.facility_type || f.latitude == null) continue;
      const d = haversineKm(c.lat, c.lon, f.latitude, f.longitude);
      if (estimateMinutes(d) <= 30) count30++;
    }
    return {
      ...row,
      nearest_minutes: Math.round(nearest.minutes * 10) / 10,
      nearest_km: nearest.km,
      facility_count_30min: count30,
    };
  });
}

/**
 * Compute before/after diff between baseline and scenario.
 */
export function scenarioDiff(baseline, scenario, popLookup) {
  let peopleAffected = 0, sa2sCrossed = 0;
  const baseByKey = new Map(baseline.map(r => [`${r.sa2_code}_${r.facility_type}`, r]));
  for (const s of scenario) {
    const key = `${s.sa2_code}_${s.facility_type}`;
    const b = baseByKey.get(key);
    if (!b) continue;
    const pop = popLookup.get(s.sa2_code) || 0;
    if (Math.abs(s.nearest_minutes - b.nearest_minutes) > 0.5) {
      peopleAffected += pop;
    }
    const bOver = b.nearest_minutes > 30;
    const sOver = s.nearest_minutes > 30;
    if (bOver !== sOver) sa2sCrossed++;
  }
  return { peopleAffected, sa2sCrossed };
}
