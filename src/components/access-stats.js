/**
 * Pure statistical functions for the access page.
 * No DOM, no Plot, no Observable globals — importable from .md files.
 */

/** Proper median: averages two middle values for even-length arrays. */
export function median(arr) {
  if (!arr.length) return null;
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 !== 0
    ? sorted[mid]
    : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** Population-weighted median. values and weights are parallel arrays. */
export function weightedMedian(values, weights) {
  if (!values.length) return null;
  const pairs = values.map((v, i) => ({ v, w: weights[i] || 0 }))
    .filter(p => p.w > 0)
    .sort((a, b) => a.v - b.v);
  const totalW = pairs.reduce((s, p) => s + p.w, 0);
  let cumW = 0;
  for (const p of pairs) {
    cumW += p.w;
    if (cumW >= totalW / 2) return p.v;
  }
  return pairs[pairs.length - 1]?.v ?? null;
}

/** Weighted percentile (0-1). */
export function weightedPercentile(values, weights, p) {
  if (!values.length) return null;
  const pairs = values.map((v, i) => ({ v, w: weights[i] || 0 }))
    .filter(d => d.w > 0)
    .sort((a, b) => a.v - b.v);
  const totalW = pairs.reduce((s, d) => s + d.w, 0);
  const target = totalW * p;
  let cumW = 0;
  for (const d of pairs) {
    cumW += d.w;
    if (cumW >= target) return d.v;
  }
  return pairs[pairs.length - 1]?.v ?? null;
}

/** Gini coefficient of a weighted distribution. 0 = equal, 1 = max inequality. */
export function gini(values, weights) {
  if (values.length < 2) return 0;
  const pairs = values.map((v, i) => ({ v, w: weights?.[i] || 1 }))
    .sort((a, b) => a.v - b.v);
  const totalW = pairs.reduce((s, p) => s + p.w, 0);
  const totalWV = pairs.reduce((s, p) => s + p.w * p.v, 0);
  if (totalWV === 0) return 0;
  let cumW = 0, cumWV = 0, giniSum = 0;
  for (const p of pairs) {
    cumW += p.w;
    cumWV += p.w * p.v;
    giniSum += p.w * (2 * cumWV - p.w * p.v);
  }
  return 1 - giniSum / (totalW * totalWV);
}

/** Pearson correlation coefficient. Returns { r, n }. */
export function pearsonR(x, y) {
  const n = Math.min(x.length, y.length);
  if (n < 3) return { r: null, n };
  const mx = x.reduce((s, v) => s + v, 0) / n;
  const my = y.reduce((s, v) => s + v, 0) / n;
  let num = 0, dx2 = 0, dy2 = 0;
  for (let i = 0; i < n; i++) {
    const dx = x[i] - mx, dy = y[i] - my;
    num += dx * dy;
    dx2 += dx * dx;
    dy2 += dy * dy;
  }
  const denom = Math.sqrt(dx2 * dy2);
  return { r: denom > 0 ? num / denom : 0, n };
}

/** Haversine distance in km. */
export function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Standard normal CDF approximation. */
function normalCDF(x) {
  const t = 1 / (1 + 0.2316419 * Math.abs(x));
  const d = 0.3989422804 * Math.exp(-x * x / 2);
  const p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.8212560 + t * 1.330274))));
  return x > 0 ? 1 - p : p;
}

/**
 * Global Moran's I with distance-based weights.
 * @param {number[]} values - travel time per SA2
 * @param {number[]} lats - SA2 centroid latitudes
 * @param {number[]} lons - SA2 centroid longitudes
 * @param {number} threshold - max distance (km) for neighbour weights
 * @returns {{I: number, z: number, p: number, expected: number}}
 */
export function moranI(values, lats, lons, threshold = 50) {
  const n = values.length;
  if (n < 10) return { I: 0, z: 0, p: 1, expected: -1 / (n - 1) };
  const mean = values.reduce((s, v) => s + v, 0) / n;
  const z = values.map(v => v - mean);
  const z2sum = z.reduce((s, v) => s + v * v, 0);
  if (z2sum === 0) return { I: 0, z: 0, p: 1, expected: -1 / (n - 1) };

  let num = 0, S0 = 0;
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      const d = haversineKm(lats[i], lons[i], lats[j], lons[j]);
      if (d > 0 && d <= threshold) {
        const w = 1 / d;
        num += w * z[i] * z[j];
        S0 += w;
      }
    }
  }
  num *= 2; // symmetric
  S0 *= 2;
  if (S0 === 0) return { I: 0, z: 0, p: 1, expected: -1 / (n - 1) };

  const I = (n * num) / (S0 * z2sum);
  const expected = -1 / (n - 1);
  // Variance under randomisation (simplified)
  const variance = 1 / (n - 1) - expected * expected; // rough approximation
  const zScore = variance > 0 ? (I - expected) / Math.sqrt(variance) : 0;
  const p = 2 * (1 - normalCDF(Math.abs(zScore)));
  return { I, z: zScore, p, expected };
}

/**
 * Local Moran's I for each location.
 * @returns {Array<{index, li, zi, lagZi, category, pValue}>}
 */
export function localMoranI(values, lats, lons, threshold = 50) {
  const n = values.length;
  const mean = values.reduce((s, v) => s + v, 0) / n;
  const variance = values.reduce((s, v) => s + (v - mean) ** 2, 0) / n;
  if (variance === 0) return values.map((_, i) => ({ index: i, li: 0, zi: 0, lagZi: 0, category: "ns", pValue: 1 }));

  const z = values.map(v => (v - mean) / Math.sqrt(variance));
  const results = [];

  for (let i = 0; i < n; i++) {
    let lagSum = 0, wSum = 0;
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      const d = haversineKm(lats[i], lons[i], lats[j], lons[j]);
      if (d > 0 && d <= threshold) {
        const w = 1 / d;
        lagSum += w * z[j];
        wSum += w;
      }
    }
    const lagZi = wSum > 0 ? lagSum / wSum : 0;
    const li = z[i] * lagZi;

    // Approximate p-value (normal approximation)
    const pValue = 2 * (1 - normalCDF(Math.abs(z[i])));

    let category = "ns"; // not significant
    if (pValue < 0.05) {
      if (z[i] > 0 && lagZi > 0) category = "HH";
      else if (z[i] < 0 && lagZi < 0) category = "LL";
      else if (z[i] > 0 && lagZi < 0) category = "HL";
      else if (z[i] < 0 && lagZi > 0) category = "LH";
    }

    results.push({ index: i, li, zi: z[i], lagZi, category, pValue });
  }
  return results;
}

/**
 * Clark-Evans nearest-neighbour R statistic for point pattern.
 * R < 1 = clustered, R ~ 1 = random, R > 1 = dispersed.
 */
export function nearestNeighbourR(lats, lons, studyAreaKm2) {
  const n = lats.length;
  if (n < 2) return { R: 1, z: 0 };
  const lambda = n / studyAreaKm2;
  const Re = 1 / (2 * Math.sqrt(lambda));

  let totalNND = 0;
  for (let i = 0; i < n; i++) {
    let minD = Infinity;
    for (let j = 0; j < n; j++) {
      if (i === j) continue;
      const d = haversineKm(lats[i], lons[i], lats[j], lons[j]);
      if (d < minD) minD = d;
    }
    totalNND += minD;
  }
  const Ro = totalNND / n;
  const R = Ro / Re;
  const se = 0.26136 / Math.sqrt(n * lambda);
  const z = (Ro - Re) / se;
  return { R: Math.round(R * 1000) / 1000, z: Math.round(z * 100) / 100, Ro: Math.round(Ro * 10) / 10, Re: Math.round(Re * 10) / 10 };
}
