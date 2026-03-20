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
