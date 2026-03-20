# Spatial Access Page Enhancements — Design Spec

**Date**: 2026-03-20
**Status**: Approved
**Scope**: Enhancements to `src/access.md` — mostly client-side, one pipeline schema change

## Context

The spatial access page (`src/access.md`) maps NZ's ~2,380 SA2 zones by deprivation and proximity to 1,252 health facilities (1,014 GPs + 238 hospitals). It uses a Leaflet interactive map with SA2 choropleth, Haversine-estimated travel times, scatter plots, and facility desert tables.

This spec covers five enhancements to make it robust, interactive, and useful as both a portfolio piece and a decision-support tool.

**Data volumes** (for performance estimation):
- 2,379 SA2 centroids (of 2,395 total — 16 have null geometry)
- 2,129 SA2s with matched NZDep data (SA2 2018→2025 concordance: ~70%)
- 1,252 facilities (1,014 GPs, 238 hospitals, 0 urgent care)
- 4,758 access rows (2,379 SA2s × 2 facility types)

## 1. Fix Stats Robustness

### Problem
- Median calculation uses `Math.floor(n/2)` — wrong for even-length arrays
- Stats are area-weighted (every SA2 counts equally) not population-weighted
- 250 SA2s (2025 codes not in 2018) lack NZDep and health_region
- Q5 median (3 min) is counterintuitive without narrative context

### Solution

**Median**: Replace with proper median function: for even n, average of values at indices n/2-1 and n/2.

**Population weighting**: The NZDep Excel has `URPopnSA1_2018` (usually-resident population per SA1 — **confirmed present** in the downloaded file). Aggregate to SA2 by summing SA1 populations within each SA2 in `sa2_boundaries.py` transformer. Add `population` column to `fact_sa2_nzdep` CREATE TABLE statement (not ALTER — `init_schema()` uses CREATE IF NOT EXISTS). Rewrite headline stats to use population-weighted metrics: "X% of *people* in Q5 areas are >30 min from a GP."

**NZDep coverage**: Show "2,129 of 2,379 SA2s matched" prominently in a note. Unmatched SA2s render as grey on the map but remain interactive. Scatter/bar charts filter to matched-only with visible annotation.

**Region assignment for unmatched SA2s**: The NZDep Excel provides `DHB_2018_name` per SA1, which maps to health region via `DHB_TO_REGION`. For the ~250 SA2s with 2025 codes not in the 2018 data, assign region by finding the nearest SA2 centroid that *does* have a region (simple Haversine nearest-neighbour in the transformer). This avoids spatial polygon operations.

**Narrative context**: Add explanatory text: "Q5 areas have the *lowest* median because most are in dense urban centres (South Auckland, Porirua) near many GPs. The equity story is in the *tail*: 15% of Q5 areas are >30 min from a GP, vs 6% of Q1."

### Pipeline change
Modify `fact_sa2_nzdep` CREATE TABLE in `pipeline/db.py` to add `population INTEGER` column. Re-run pipeline to populate. This is a schema modification to an existing table, not a new pipeline stage.

### Files changed
- `pipeline/db.py` — add `population` column to `fact_sa2_nzdep` CREATE TABLE
- `pipeline/transform/sa2_boundaries.py` — aggregate population from `URPopnSA1_2018`, assign region to unmatched SA2s via nearest-neighbour
- `src/access.md` — fix median, use population weighting, add coverage caveats and narrative context

## 2. Click-to-Detail Panel

### Interaction
Click any SA2 polygon or facility marker on the Leaflet map. A panel appears (Leaflet popup) showing contextual detail.

### SA2 click shows:
- SA2 name, NZDep quintile + score, population
- Nearest GP: name, distance (km), estimated drive time (min)
- Nearest hospital: name, distance (km), estimated drive time (min)
- Comparison to national median (e.g. "2x the national median drive time")
- Count of facilities within 30 min

**Note**: `fact_access` stores nearest time/distance but not facility name. The nearest facility name is computed client-side on click by scanning the loaded facilities array for the one closest (by Haversine) to the SA2 centroid. With 1,252 facilities this is <1ms.

### Facility click shows:
- Facility name, type (GP/hospital)
- SA2 it's located in, NZDep quintile of that SA2
- Number of SA2s for which this is the nearest facility of its type (computed client-side: count SA2 centroids closer to this facility than any other of the same type)

### Files changed
- `src/access.md` — add click handlers to Leaflet layers, build popup content

## 3. What-If Scenario Engine

### Design philosophy
Scenarios model **modifications to existing entities**, not abstract pin-drops. The user clicks a real facility or area and adjusts it. This models realistic policy decisions.

### Important methodology note
All scenario travel time estimates use **Haversine distance × winding factor** (same as the baseline data). Scenarios do not call OSRM. Results are clearly labelled as estimates. This is consistent because the baseline data already uses Haversine estimation.

### Facility-level scenarios (click a facility marker)
- **Adjust capacity / remove**: slider 0%–200%. At 0% = closure. Affected SA2s (those where this was the nearest facility) are identified client-side and rerouted to next-nearest by scanning the remaining facilities list via Haversine. Map recolours affected SA2s.
- **Remove facility**: one-click closure shortcut. Same rerouting logic.

**Rerouting approach**: Since `fact_access` only stores the single nearest facility, closure rerouting recomputes from the full facilities list client-side. For each affected SA2, scan all remaining facilities of that type, find the nearest by Haversine, apply winding factor + speed estimate. With ~200 affected SA2s × 1,000 facilities, this is ~200K Haversine calculations — sub-100ms in JS.

### Area-level scenarios (click an SA2 or select a health region)
- **Telehealth rollout**: toggle that caps effective travel time for the selected area (e.g. max 15 min for GP access). Models remote consultation access.
- **Transport barrier**: fuel cost multiplier (1x–3x) applied to travel times for that area's SA2s. Shows how transport costs degrade access for specific communities.
- **Funding cut**: slider 0%–100% that removes facilities in the selected area, starting with those serving the fewest SA2s. Shows cascade effect.

### Global scenarios (controls above the map)
- **Fuel price shock**: slider (1x–3x) affecting all travel times nationally
- **Pandemic mode**: randomly removes X% of facilities (seeded for reproducibility), shows system fragility
- **Universal telehealth**: blanket travel time cap (configurable: 10/15/20 min)

### Performance
All client-side. Worst case: pandemic mode removing 30% of facilities → ~2,400 SA2s × 1,252 facilities × Haversine = ~3M calculations. Haversine is ~100ns each in JS, so ~300ms total. **Debounce slider inputs at 300ms** and show a brief "Recalculating..." indicator.

### Before/after summary
When any scenario is active, a comparison panel shows:
- Facilities affected (removed/modified)
- People affected (population-weighted, using `fact_sa2_nzdep.population`)
- SA2s that crossed the 30-min threshold (in either direction)
- Change in Q5 median drive time (population-weighted)
- Change in access Gini coefficient

### Files changed
- `src/access.md` — scenario UI controls, reactive updates
- `src/components/scenario-engine.js` — extracted scenario logic: `applyScenario(baseData, facilities, centroids, params) → scenarioData`

## 4. Autoresearcher Connection

### Current state
The autoresearch page (`src/autoresearch.md`) simulates 887 healthcare configurations for Counties Manukau. Data is in:
- `sim_agents.parquet` — columns: `agent_id`, `strategy`, `accepted` (bool), `overall_score`, `cost_efficiency`, `coverage`, `wait_time`
- `sim_metrics.parquet` — time-series metrics per agent
- `sim_causal.parquet` — causal relationship strengths

The sim data outputs aggregate metrics, not facility-level coordinates.

### Phase 1 (this spec): Region overlay + link
- Toggle on the access map: "Show autoresearch focus area"
- Highlights Counties Manukau SA2s with a distinct dashed border
- Reads `sim_agents.parquet`, filters to `accepted = true`, sorts by `overall_score DESC`, takes the top row
- Displays summary: strategy name, overall score, coverage %, wait time, cost efficiency
- "View full analysis →" link to `/autoresearch`
- If a scenario is active, shows comparison: "your scenario vs autoresearch best"

### Phase 2 (future): Facility-level recommendations
When the autoresearcher evolves to output facility coordinates, overlay proposed markers and compute counterfactual travel times.

### Files changed
- `src/access.md` — toggle control, Counties Manukau SA2 highlight, summary panel, load `sim_agents.parquet`

## 5. Analyst Layer

### CSV export
Button: "Download data (CSV)". Exports the current view — filtered by active scenario, facility type, and region selection. Columns:

```
sa2_code, sa2_name, nzdep_quintile, nzdep_score, population, health_region,
nearest_gp_minutes, nearest_gp_km,
nearest_hospital_minutes, nearest_hospital_km,
facilities_within_30min, scenario_label
```

Nearest facility **name** is omitted from the CSV (not stored in access table; would require expensive recomputation for all rows). When a scenario is active, includes both baseline and scenario columns for comparison.

### Summary statistics panel
Collapsible section below the map showing:
- Distribution: mean, median, P25, P75, P90 travel time by quintile (population-weighted)
- Gini coefficient of access inequality: computed as the Gini index of the population-weighted travel time distribution across all SA2s. Formula: `G = (2 * sum(i * w_i * t_i)) / (n * sum(w_i * t_i)) - (n+1)/n` where `w_i` is population weight and `t_i` is travel time, sorted ascending. Range 0 (perfect equality) to 1 (total inequality).
- Pearson correlation: NZDep score vs travel time (r value + n)
- Population coverage: % of people within 15/30/45/60 min by quintile
- When scenario active: delta for each stat vs baseline

### Cross-tabulation table
Pivot: health region (rows) × NZDep quintile (columns). Cell value: population-weighted median travel time. Second table: population count per cell. These are the tables an analyst would copy into a report.

### SQL console (stretch goal)
Expose DuckDB-WASM via `Inputs.text` → `db.query()`. Pre-populated with example queries. **Safe because DuckDB-WASM runs entirely in the browser sandbox against read-only parquet files** — no server, no mutation possible.

### Files changed
- `src/access.md` — export button, stats panel, cross-tab table
- `src/components/access-stats.js` — extracted stats computation (Gini, correlation, weighted percentiles)

## Implementation order

1. **Stats fixes** (pipeline schema change + re-run + page update) — foundation for everything else. Start with the schema/pipeline change, verify data, then update the page.
2. **Click-to-detail** — small, self-contained, immediate UX win
3. **Analyst layer** — CSV export + stats panel, needed before scenarios (so analysts can export scenario results)
4. **What-if scenarios** — the big feature, depends on correct stats and analyst layer for validation
5. **Autoresearcher connection** — depends on scenarios being in place

## Non-goals
- No new pipeline fetchers
- No server-side computation
- No user accounts or saved scenarios (stateless)
- No mobile-specific layout (desktop-first is fine for portfolio)
- No OSRM routing in scenarios (Haversine estimation is consistent with baseline)
