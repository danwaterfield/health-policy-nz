# Access Page Enhancements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the spatial access page robust, interactive, and analytically powerful — fixing stats, adding click-to-detail, what-if scenarios, autoresearcher integration, spatial statistics, and analyst tools.

**Architecture:** All enhancements are client-side JS in Observable Framework except Task 1 (pipeline schema change). The page (`src/access.md`) is the main file; complex logic is extracted into `src/components/` JS modules. Data flows: parquet → DuckDB-WASM → JS arrays → Leaflet map + Observable Plot charts.

**Tech Stack:** Observable Framework, Leaflet, DuckDB-WASM, D3, Plot. Pipeline: Python 3.12, DuckDB, pandas.

**Spec:** `docs/superpowers/specs/2025-03-20-access-page-enhancements-design.md`

---

## File Structure

### New files
- `src/components/access-stats.js` — pure functions: `median()`, `weightedMedian()`, `gini()`, `pearsonR()`, `moranI()`, `localMoranI()`, `nearestNeighbourR()`, `weightedPercentile()`
- `src/components/scenario-engine.js` — pure functions: `applyScenario()`, `computeAccessForSA2()`, `haversineKm()`, `scenarioDiff()`
- `src/components/access-detail.js` — `buildSA2Popup()`, `buildFacilityPopup()`, `findNearestFacility()`

### Modified files
- `pipeline/db.py` — add `population` column to `fact_sa2_nzdep` CREATE TABLE
- `pipeline/transform/sa2_boundaries.py` — aggregate population, assign region to unmatched SA2s
- `src/access.md` — all UI changes (stats cards, click handlers, scenario controls, analyst panel, caveats)

### Test files
- `tests/test_sa2_population.py` — verify population aggregation and region assignment

---

## Task 1: Stats Robustness — Pipeline Changes

**Files:**
- Modify: `pipeline/db.py:309` (fact_sa2_nzdep CREATE TABLE)
- Modify: `pipeline/transform/sa2_boundaries.py:100-140` (_aggregate_nzdep_to_sa2 method)
- Create: `tests/test_sa2_population.py`

- [ ] **Step 1: Write test for population aggregation**

```python
# tests/test_sa2_population.py
"""Test SA2 population aggregation from SA1 data."""
import duckdb
from pipeline.db import init_schema
from pipeline.transform.sa2_boundaries import SA2BoundariesTransformer
from pathlib import Path
import json

def test_population_aggregated():
    """SA2 NZDep rows should have non-null population from SA1 aggregation."""
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    t = SA2BoundariesTransformer()
    t.transform(Path("data/lookups/sa2_2025_simplified.geojson"), conn)
    rows = conn.execute(
        "SELECT COUNT(*) as total, "
        "COUNT(population) as with_pop, "
        "SUM(population) as total_pop "
        "FROM fact_sa2_nzdep"
    ).fetchone()
    conn.close()
    assert rows[0] > 2000, f"Expected >2000 SA2 NZDep rows, got {rows[0]}"
    assert rows[1] == rows[0], f"All rows should have population, {rows[0] - rows[1]} missing"
    assert rows[2] > 4_000_000, f"Total NZ pop should be >4M, got {rows[2]}"

def test_region_assigned_to_all():
    """All SA2 NZDep rows should have a health_region."""
    conn = duckdb.connect(":memory:")
    init_schema(conn)
    t = SA2BoundariesTransformer()
    t.transform(Path("data/lookups/sa2_2025_simplified.geojson"), conn)
    missing = conn.execute(
        "SELECT COUNT(*) FROM fact_sa2_nzdep WHERE health_region = '' OR health_region IS NULL"
    ).fetchone()[0]
    conn.close()
    assert missing == 0, f"{missing} SA2s missing health_region"
```

- [ ] **Step 2: Run tests — expect FAIL** (population column doesn't exist yet)

Run: `python3.12 -m pytest tests/test_sa2_population.py -v`
Expected: FAIL — column `population` not found

- [ ] **Step 3: Add population column to schema**

In `pipeline/db.py`, find the `fact_sa2_nzdep` CREATE TABLE and add `population INTEGER` after `sa1_count`:

```sql
CREATE TABLE IF NOT EXISTS fact_sa2_nzdep (
    id INTEGER PRIMARY KEY,
    sa2_code VARCHAR,
    sa2_name VARCHAR,
    nzdep_mean_score DOUBLE,
    nzdep_quintile INTEGER,
    sa1_count INTEGER,
    population INTEGER,
    health_region VARCHAR,
    source VARCHAR
);
```

- [ ] **Step 4: Update sa2_boundaries.py to aggregate population and fix region gaps**

In `_aggregate_nzdep_to_sa2()`, add population aggregation from `URPopnSA1_2018`:

```python
df["population"] = pd.to_numeric(df["URPopnSA1_2018"], errors="coerce").fillna(0).astype(int)
```

In the groupby loop, sum population:

```python
result[sa2_code] = {
    "score": float(scores.mean()),
    "quintile": quintile,
    "sa1_count": len(scores),
    "population": int(group["population"].sum()),
    "sa2_name": group["sa2_name"].iloc[0],
    "health_region": region,
}
```

After the aggregation loop, add region assignment for unmatched SA2s:

```python
# Assign region to unmatched SA2s via nearest-neighbour
sa2s_with_region = [(c["lat"], c["lon"], c["health_region"])
                     for c in centroids if c.get("health_region")]
for c in centroids:
    if not c.get("health_region") and c["lat"] != 0:
        best_dist = float("inf")
        for rlat, rlon, region in sa2s_with_region:
            d = (c["lat"] - rlat)**2 + (c["lon"] - rlon)**2
            if d < best_dist:
                best_dist = d
                c["health_region"] = region
```

Update the `_load_sa2_nzdep()` INSERT to include `population`:

```python
conn.execute("""
    INSERT INTO fact_sa2_nzdep
        (id, sa2_code, sa2_name, nzdep_mean_score, nzdep_quintile,
         sa1_count, population, health_region, source)
    VALUES (nextval('fact_sa2_nzdep_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    sa2_code, data.get("sa2_name", ""), data.get("score"),
    data.get("quintile"), data.get("sa1_count", 0),
    data.get("population", 0), data.get("health_region", ""),
    "NZDep2018 SA1→SA2 aggregation",
))
```

- [ ] **Step 5: Delete DuckDB and seed, re-run pipeline**

```bash
rm -f data/nz_health.duckdb data/lookups/travel_time_seed.csv
python3.12 -m pipeline.run_all
make copy-data
```

- [ ] **Step 6: Run tests — expect PASS**

```bash
python3.12 -m pytest tests/test_sa2_population.py tests/ -v
```
Expected: All tests PASS including existing 23 tests

- [ ] **Step 7: Commit**

```bash
git add pipeline/db.py pipeline/transform/sa2_boundaries.py tests/test_sa2_population.py \
  data/lookups/travel_time_seed.csv src/data/fact_sa2_nzdep.parquet src/data/fact_access.parquet \
  src/data/sa2-centroids.json
git commit -m "feat: add population weighting and fix region assignment for SA2 NZDep data"
```

---

## Task 2: Stats Robustness — Page Updates

**Files:**
- Create: `src/components/access-stats.js`
- Modify: `src/access.md`

- [ ] **Step 1: Create access-stats.js with core stat functions**

```js
// src/components/access-stats.js
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

/** Pearson correlation coefficient between two arrays. Returns { r, n }. */
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
```

- [ ] **Step 2: Update access.md — import stats, fix median, add population weighting and caveats**

In the imports block at the top of `src/access.md`, add:

```js
import {median, weightedMedian, weightedPercentile, gini, pearsonR, haversineKm} from "./components/access-stats.js";
```

Replace the key statistics section's inline median calculation with `weightedMedian()`. Add population lookup from `sa2Nzdep`. Add narrative context about Q5 urban concentration. Add "2,129 of 2,379 SA2s matched" note. Full code in the step — see spec Section 1 for the exact narrative text.

- [ ] **Step 3: Build site and verify**

```bash
npm run build 2>&1 | tail -3
```
Expected: `ok (no errors)`

- [ ] **Step 4: Commit**

```bash
git add src/components/access-stats.js src/access.md
git commit -m "feat: add population-weighted stats, proper median, and coverage caveats"
```

---

## Task 3: Click-to-Detail Panel

**Files:**
- Create: `src/components/access-detail.js`
- Modify: `src/access.md`

- [ ] **Step 1: Create access-detail.js**

Build functions that generate HTML strings for Leaflet popups. `buildSA2Popup(sa2Code, accessLookup, nzdepLookup, facilities, centroids, nationalMedian)` and `buildFacilityPopup(facility, nzdepLookup, centroids)`. Uses `haversineKm` from access-stats.js. `findNearestFacility(lat, lon, facilities, type)` scans facilities array and returns `{name, distance_km, minutes}`.

- [ ] **Step 2: Wire popups into Leaflet layers in access.md**

Replace the SA2 layer's `bindTooltip` with `bindPopup` using `buildSA2Popup()` on click. Keep `bindTooltip` for hover. Add `bindPopup` to facility markers using `buildFacilityPopup()`.

- [ ] **Step 3: Build and verify**

```bash
npm run build 2>&1 | tail -3
```

- [ ] **Step 4: Commit**

```bash
git add src/components/access-detail.js src/access.md
git commit -m "feat: add click-to-detail popups for SA2 areas and facilities"
```

---

## Task 4: Analyst Layer — CSV Export and Summary Stats

**Files:**
- Modify: `src/access.md`
- Modify: `src/components/access-stats.js` (add Moran's I, LISA, nearest-neighbour R)

- [ ] **Step 1: Add CSV export button to access.md**

Add a "Download data (CSV)" button that generates a CSV from the current `filteredAccess` data joined with `sa2Nzdep` for population/quintile. Uses `URL.createObjectURL(new Blob([csvString]))` and a temporary `<a>` element. Include scenario label column if scenario is active.

- [ ] **Step 2: Add summary statistics panel**

Collapsible `<details>` section below the scatter plot. Computes: weighted mean, weighted median, P25/P75/P90 by quintile. Gini coefficient. Pearson r (NZDep score vs travel time). Population coverage table (% within 15/30/45/60 min by quintile). Uses functions from `access-stats.js`.

- [ ] **Step 3: Add cross-tabulation table**

Pivot table: health region rows × NZDep quintile columns. Cell = population-weighted median travel time. Second table = population count. Computed from `filteredAccess` joined with `sa2Nzdep`. Uses `Inputs.table()`.

- [ ] **Step 4: Add spatial statistics to access-stats.js**

Add `moranI(values, lats, lons, distanceThreshold)` — global Moran's I with distance-based weights. Add `localMoranI(values, lats, lons, distanceThreshold)` — returns array of `{sa2_code, li, zi, category, pValue}`. Add `nearestNeighbourR(lats, lons, studyAreaKm2)` — Clark-Evans R statistic. Performance note: Moran's I with n=2,000 uses a distance threshold to create a sparse weight matrix. At 50km threshold, each SA2 has ~50-200 neighbours, so the computation is O(n * avg_neighbours) ≈ 200K, not O(n^2).

- [ ] **Step 5: Add LISA hotspot layer toggle to the map**

Add a checkbox: "Show access hotspots (LISA)". When toggled, computes local Moran's I and overlays significant HH/LL/HL/LH clusters as coloured borders on SA2 polygons. HH = red dashed border (structurally underserved), LL = blue dashed (well-served), HL/LH = grey. Add Moran's I, R statistic, and LISA summary to the stats panel.

- [ ] **Step 6: Add methodology caveats to page footer**

Add the MAUP, ecological fallacy, boundary effects, and spatial autocorrelation caveats from the spec to the existing methodology section at the bottom of `access.md`.

- [ ] **Step 7: Build and verify**

```bash
npm run build 2>&1 | tail -3
```

- [ ] **Step 8: Commit**

```bash
git add src/components/access-stats.js src/access.md
git commit -m "feat: add analyst layer — CSV export, summary stats, spatial statistics (Moran's I, LISA), and methodology caveats"
```

---

## Task 5: What-If Scenario Engine

**Files:**
- Create: `src/components/scenario-engine.js`
- Modify: `src/access.md`

- [ ] **Step 1: Create scenario-engine.js with core functions**

Pure functions, no DOM. Key exports:

- `haversineKm(lat1, lon1, lat2, lon2)` — import from access-stats.js or duplicate
- `findNearestFacility(lat, lon, facilities, type)` — returns `{name, lat, lon, minutes, km}`
- `removeFacility(facilityIndex, facilities, centroids, accessData)` — returns new access array with rerouted SA2s
- `applyFuelMultiplier(accessData, multiplier, region)` — returns new access array with scaled times
- `applyTelehealthCap(accessData, capMinutes, region)` — caps travel times
- `removeFacilitiesByPercent(facilities, centroids, accessData, pct, seed)` — pandemic mode
- `scenarioDiff(baseline, scenario, populationLookup)` — returns `{facilitiesAffected, peopleAffected, sa2sCrossed30min, q5MedianDelta, giniDelta}`

All functions return new arrays (immutable). Winding factor (1.4) and speed constants (35/55 km/h) imported or duplicated from the pipeline constants.

- [ ] **Step 2: Add global scenario controls to access.md**

Above the map, add controls in a collapsible panel:
- Fuel price slider (1x–3x) with debounce
- Telehealth toggle + cap selector (10/15/20 min)
- Pandemic mode slider (0%–50% facility removal)
- Reset button

Each control updates a reactive `scenarioParams` object. A derived `scenarioData` is computed via `applyScenario()`. The map, stats, scatter, and table all read from `scenarioData` instead of raw `accessData` when a scenario is active.

- [ ] **Step 3: Add facility-level scenario controls**

When a facility is clicked and scenario mode is active, the popup includes:
- "Remove this facility" button → calls `removeFacility()`, updates `scenarioData`
- The map recolours affected SA2s

- [ ] **Step 4: Add area-level scenario controls**

When a health region is selected from a dropdown:
- Fuel multiplier for that region only
- Telehealth toggle for that region
- Funding cut slider for that region

- [ ] **Step 5: Add before/after summary panel**

When any scenario is active, show a comparison card:
- Facilities removed/modified
- People affected (population-weighted)
- SA2s crossing 30-min threshold
- Q5 median delta
- Gini delta

Uses `scenarioDiff()`.

- [ ] **Step 6: Build and verify**

```bash
npm run build 2>&1 | tail -3
```

- [ ] **Step 7: Commit**

```bash
git add src/components/scenario-engine.js src/access.md
git commit -m "feat: add what-if scenario engine — facility removal, fuel shock, telehealth, pandemic mode"
```

---

## Task 6: Autoresearcher Connection

**Files:**
- Modify: `src/access.md`

- [ ] **Step 1: Load sim_agents.parquet in access.md**

Add to the DuckDB client:

```js
sim_agents: FileAttachment("data/sim_agents.parquet"),
```

Query the top accepted configuration:

```js
const topAgent = Array.from(await db.query(`
  SELECT * FROM sim_agents WHERE accepted = true ORDER BY overall_score DESC LIMIT 1
`))[0];
```

- [ ] **Step 2: Add Counties Manukau overlay toggle**

Checkbox: "Show autoresearch focus area". When toggled:
- Highlights Counties Manukau SA2s (health_region = "Northern | Te Tai Tokerau" AND sa2_name matches Counties Manukau area) with dashed purple border
- Shows summary card with top agent's strategy, overall score, coverage, wait time, cost efficiency
- Link to `/autoresearch`

Note: Counties Manukau is part of the Northern health region. Need to identify which SA2s are in the Counties Manukau area — can match on the SA2 name or use a list.

- [ ] **Step 3: Build and verify**

```bash
npm run build 2>&1 | tail -3
```

- [ ] **Step 4: Commit**

```bash
git add src/access.md
git commit -m "feat: add autoresearcher connection — Counties Manukau overlay and top config summary"
```

---

## Task 7: Final Integration and Polish

- [ ] **Step 1: Run full test suite**

```bash
python3.12 -m pytest tests/ -v
```
Expected: All tests pass (23 existing + 2 new)

- [ ] **Step 2: Full pipeline run + build**

```bash
python3.12 -m pipeline.run_all
make copy-data
npm run build
```

- [ ] **Step 3: Visual review**

```bash
npm run dev
```
Check each section of `/access`: stats cards, map, click popups, scatter, bar chart, facility deserts, analyst stats, CSV export, LISA layer, scenario controls, autoresearch overlay.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "polish: final integration and cleanup for access page enhancements"
```
