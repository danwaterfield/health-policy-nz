# Spatial Access Page Enhancements — Design Spec

**Date**: 2025-03-20
**Status**: Approved
**Scope**: Enhancements to `src/access.md` — all client-side, no new pipeline stages

## Context

The spatial access page (`src/access.md`) maps NZ's 2,395 SA2 zones by deprivation and proximity to 1,252 health facilities (GPs + hospitals). It uses a Leaflet interactive map with SA2 choropleth, travel time estimates, scatter plots, and facility desert tables.

This spec covers five enhancements to make it robust, interactive, and useful as both a portfolio piece and a decision-support tool.

## 1. Fix Stats Robustness

### Problem
- Median calculation uses `Math.floor(n/2)` — wrong for even-length arrays
- Stats are area-weighted (every SA2 counts equally) not population-weighted
- 816 access rows (34%) lack NZDep quintile due to SA2 2025/2018 code mismatch
- 363 facilities and 816 access rows lack health_region assignment

### Solution

**Median**: Replace with proper median function: for even n, average of values at indices n/2-1 and n/2.

**Population weighting**: The NZDep Excel has `URPopnSA1_2018` (usually-resident population per SA1). Aggregate to SA2 in `sa2_boundaries.py` transformer. Add `population` column to `fact_sa2_nzdep` table. Rewrite stats to use population-weighted metrics: "X% of *people* in Q5 areas are >30 min from a GP."

**NZDep coverage**: Show "N of M SA2s matched" prominently. Unmatched SA2s render as grey on the map. Scatter/bar charts filter to matched-only with a note.

**Region assignment**: Currently region flows through NZDep→DHB chain, which fails for unmatched SA2s. Fix by computing region from SA2 centroid position: find nearest DHB boundary centroid. This is a one-time spatial lookup in the SA2 transformer, stored in the centroids JSON.

### Schema change
```sql
-- Add population column to fact_sa2_nzdep
ALTER TABLE fact_sa2_nzdep ADD COLUMN population INTEGER;
```

### Files changed
- `pipeline/transform/sa2_boundaries.py` — aggregate population, assign region to all SA2s
- `src/access.md` — fix median, use population weighting, add coverage caveats

## 2. Click-to-Detail Panel

### Interaction
Click any SA2 polygon or facility marker on the Leaflet map. A panel appears (Leaflet popup or side div) showing contextual detail.

### SA2 click shows:
- SA2 name, NZDep quintile + score, population
- Nearest GP: name, distance (km), estimated drive time (min)
- Nearest hospital: name, distance (km), estimated drive time (min)
- Comparison to national median (e.g. "2x the national median drive time")
- Count of facilities within 30 min

### Facility click shows:
- Facility name, type (GP/hospital)
- SA2 it's located in, NZDep quintile of that SA2
- Number of SA2s for which this is the nearest facility of its type

### Implementation
All data is already loaded client-side in DuckDB-WASM. Panel content is computed on click from existing parquet tables. No new data fetches.

### Files changed
- `src/access.md` — add click handlers to Leaflet layers, build popup/panel HTML

## 3. What-If Scenario Engine

### Design philosophy
Scenarios model **modifications to existing entities**, not abstract pin-drops. The user clicks a real facility or area and adjusts it. This models realistic policy decisions.

### Facility-level scenarios (click a facility marker)
- **Adjust capacity**: slider 0%–200%. At 0% = closure. Affects routing: SA2s that relied on a closed facility reroute to next-nearest. Map recolours affected SA2s.
- **Remove facility**: one-click closure shortcut. Shows blast radius.
- **Change type**: convert GP to urgent care or vice versa.

### Area-level scenarios (click an SA2 or select a health region)
- **Funding adjustment**: slider that scales effective facility count in the area. "+50%" adds synthetic facilities at underserved SA2 centroids. "-30%" removes lowest-capacity facilities.
- **Telehealth rollout**: toggle that caps effective travel time for the selected area (e.g. max 15 min for GP access). Models remote consultation access.
- **Transport barrier**: fuel cost multiplier (1x–3x) applied to travel times for that area's SA2s. Shows how transport costs degrade access for specific communities.

### Global scenarios (controls above the map)
- **Fuel price shock**: slider affecting all travel times nationally
- **Pandemic mode**: randomly removes X% of facilities, shows system fragility
- **Universal telehealth**: blanket travel time cap

### Computation
All client-side. Each scenario applies a transformation function to the loaded access data array:
```
scenarioData = applyScenario(baseAccessData, scenarioParams)
```
The map, stats, scatter, and table all reactively update from `scenarioData`.

### Before/after summary
When any scenario is active, a comparison panel shows:
- Facilities affected (added/removed/modified)
- People affected (population in changed SA2s)
- SA2s that crossed the 30-min threshold (in either direction)
- Change in Q5 median drive time
- Change in access Gini coefficient

### Files changed
- `src/access.md` — scenario UI controls, transformation functions, reactive updates
- `src/components/scenario-engine.js` — extracted scenario logic (keeps access.md manageable)

## 4. Autoresearcher Connection

### Current state
The autoresearch page (`src/autoresearch.md`) simulates 887 healthcare configurations for Counties Manukau. Data is in `sim_agents.parquet` (accepted/rejected configs), `sim_metrics.parquet` (performance metrics), `sim_causal.parquet` (causal relationships).

The sim data outputs aggregate metrics, not facility-level coordinates.

### Phase 1 (this spec): Region overlay + link
- Toggle on the access map: "Show autoresearch focus area"
- Highlights Counties Manukau SA2s with a distinct border style
- Overlays text summary of the top-ranked configuration's key metrics
- "View full analysis" link to `/autoresearch`
- If a scenario is active, show comparison: "current scenario vs autoresearch recommendation"

### Phase 2 (future): Facility-level recommendations
When the autoresearcher evolves to output facility coordinates:
- Overlay proposed facility markers (different icon — e.g. dashed circle)
- Compute counterfactual travel times for the focus area
- Before/after choropleth within the focus region

### Files changed
- `src/access.md` — toggle control, Counties Manukau highlight, summary panel

## 5. Analyst Layer

### CSV export
Button: "Download data (CSV)". Exports the current view — filtered by active scenario, facility type, and region selection. Columns:

```
sa2_code, sa2_name, nzdep_quintile, nzdep_score, population, health_region,
nearest_gp_name, nearest_gp_minutes, nearest_gp_km,
nearest_hospital_name, nearest_hospital_minutes, nearest_hospital_km,
facilities_within_30min, scenario_label
```

When a scenario is active, includes both baseline and scenario columns for comparison.

### Summary statistics panel
Collapsible section below the map showing:
- Distribution: mean, median, P25, P75, P90 travel time by quintile
- Gini coefficient of access inequality
- Pearson correlation: NZDep score vs travel time (r + significance)
- Population coverage: % of people within 15/30/45/60 min by quintile
- When scenario active: delta for each stat vs baseline

### Cross-tabulation table
Pivot: health region (rows) x NZDep quintile (columns). Cell value: median travel time (population-weighted). Second table: population count per cell. These are the tables an analyst would copy into a report.

### SQL console (stretch goal)
Expose DuckDB-WASM via `Inputs.text` → `db.query()`. Lets analysts write arbitrary SQL against the parquet files. Pre-populated with example queries. Only if time permits.

### Files changed
- `src/access.md` — export button, stats panel, cross-tab table
- `src/components/access-stats.js` — extracted stats computation (Gini, correlation, etc.)

## Implementation order

1. Stats fixes (pipeline change + page update) — foundation for everything else
2. Click-to-detail — small, self-contained, immediate UX win
3. Analyst layer — CSV export + stats panel, needed before scenarios (so analysts can export scenario results)
4. What-if scenarios — the big feature, depends on correct stats
5. Autoresearcher connection — depends on scenarios being in place

## Non-goals
- No new pipeline stages or fetchers
- No server-side computation
- No user accounts or saved scenarios (stateless)
- No mobile-specific layout (desktop-first is fine for portfolio)
