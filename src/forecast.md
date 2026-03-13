---
title: Demand Forecast
---

# Demand Forecast

Projected health service demand under Stats NZ demographic scenarios.

```js
import {dataFreshness} from "./components/data-freshness.js";
```

```js
const db = await DuckDBClient.of({
  fact_demand_projection: FileAttachment("data/fact_demand_projection.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
  dim_data_source: FileAttachment("data/dim_data_source.parquet"),
});
```

```js
// Load available service types and geographies
const serviceTypes = Array.from(await db.query(`
  SELECT DISTINCT service_type FROM fact_demand_projection ORDER BY service_type
`));

const geographies = Array.from(await db.query(`
  SELECT DISTINCT g.id, g.name, g.level
  FROM fact_demand_projection fdp
  JOIN dim_geography g ON fdp.geography_id = g.id
  ORDER BY g.level, g.name
`));
```

```js
// Selectors
const selectedService = view(Inputs.select(
  serviceTypes.map(d => d.service_type),
  { label: "Service type", value: serviceTypes[0]?.service_type }
));

const selectedGeo = view(Inputs.select(
  new Map(geographies.map(d => [d.name, d.id])),
  { label: "Region", value: geographies.find(d => d.level === "national")?.id ?? geographies[0]?.id }
));
```

```js
// Validate inputs against known values before interpolating into SQL
const serviceMap = new Map(serviceTypes.map(d => [d.service_type, d.service_type]));
const knownGeoIds = geographies.map(d => d.id);
const safeService = serviceMap.get(selectedService) ?? null;
const safeGeoId = knownGeoIds.includes(selectedGeo) ? selectedGeo : null;

// Query projection data for all scenarios — aggregate sub-projections per year
const projections = (safeService && safeGeoId != null) ? Array.from(await db.query(`
  SELECT
    fdp.scenario,
    SUM(fdp.projected_volume) AS projected_volume,
    SUM(fdp.capacity_gap)    AS capacity_gap,
    t.year
  FROM fact_demand_projection fdp
  JOIN dim_time t ON fdp.time_id = t.id
  WHERE fdp.service_type = '${safeService}'
    AND fdp.geography_id = ${safeGeoId}
  GROUP BY fdp.scenario, t.year
  ORDER BY t.year, fdp.scenario
`)) : [];

const hasData = projections.length > 0;
```

```js
const serviceDisplayName = (s) => {
  const map = {
    "ed": "Emergency Department",
    "fsa": "First Specialist Assessment",
    "primary_care_gp_visits": "Primary Care (GP Visits)",
    "aged_residential_care": "Aged Residential Care",
    "mental_health": "Mental Health",
  };
  return map[s] ?? s.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
};
```

## Demand Projections — ${serviceDisplayName(selectedService)}

```js
if (!hasData) {
  display(html`
    <div style="padding: 2rem; background: #f5f5f5; border-radius: 8px; color: #333;">
      <p><strong>No projection data available</strong></p>
      <p>Projection data has not yet been ingested for this selection.</p>
    </div>
  `);
} else {
  const baseline = projections.filter(d => d.scenario === "baseline");
  const high = projections.filter(d => d.scenario === "high");
  const low = projections.filter(d => d.scenario === "low");

  display(Plot.plot({
    title: `Projected demand — ${serviceDisplayName(selectedService)}`,
    marginLeft: 80,
    marginRight: 70,
    width,
    y: { label: "Projected volume" },
    x: { label: "Year" },
    marks: [
      // Projection start marker
      Plot.ruleX([2023], { stroke: "#666", strokeDasharray: "6,3", strokeWidth: 1 }),
      Plot.text([{ year: 2023 }], {
        x: "year",
        frameAnchor: "top",
        dy: 6,
        dx: 4,
        text: () => "Projections start →",
        fontSize: 9,
        fill: "#555",
        textAnchor: "start",
        fontStyle: "italic",
      }),
      // Uncertainty band (low to high)
      Plot.areaY(
        projections.filter(d => d.scenario !== "baseline"),
        Plot.groupX(
          { y1: "min", y2: "max" },
          { x: "year", y: "projected_volume", fill: "#1f77b4", fillOpacity: 0.15, tip: true }
        )
      ),
      // Scenario lines
      Plot.lineY(low, {
        x: "year", y: "projected_volume",
        stroke: "#aec7e8", strokeWidth: 1.5, strokeDasharray: "4,4",
        tip: true,
        title: d => `Low scenario: ${d.projected_volume?.toFixed(0)}`,
      }),
      Plot.lineY(high, {
        x: "year", y: "projected_volume",
        stroke: "#aec7e8", strokeWidth: 1.5, strokeDasharray: "4,4",
        tip: true,
        title: d => `High scenario: ${d.projected_volume?.toFixed(0)}`,
      }),
      // Baseline
      Plot.lineY(baseline, {
        x: "year", y: "projected_volume",
        stroke: "#1f77b4", strokeWidth: 2.5,
        tip: true,
        title: d => `Baseline: ${d.projected_volume?.toFixed(0)}`,
      }),
      Plot.dot(baseline, {
        x: "year", y: "projected_volume",
        fill: "#1f77b4",
        symbol: "circle",
        tip: true,
        title: d => `${d.year}: ${d.projected_volume?.toFixed(0)} (baseline)`,
      }),
      // Direct line labels at endpoints (reduce legend lookup)
      baseline.length > 0 ? Plot.text([baseline[baseline.length - 1]], {
        x: "year", y: "projected_volume",
        text: () => "Baseline",
        dx: 6, textAnchor: "start", fontSize: 10, fill: "#1f77b4", fontWeight: "600",
      }) : null,
      high.length > 0 ? Plot.text([high[high.length - 1]], {
        x: "year", y: "projected_volume",
        text: () => "High",
        dx: 6, textAnchor: "start", fontSize: 9, fill: "#aec7e8",
      }) : null,
      low.length > 0 ? Plot.text([low[low.length - 1]], {
        x: "year", y: "projected_volume",
        text: () => "Low",
        dx: 6, textAnchor: "start", fontSize: 9, fill: "#aec7e8",
      }) : null,
    ].filter(Boolean),
  }));

  // Legend
  display(html`
    <div style="display: flex; gap: 1.5rem; font-size: 0.9rem; margin: 0.5rem 0 1rem;">
      <span><span style="color: #1f77b4; font-weight: bold;">—</span> Baseline</span>
      <span><span style="color: #aec7e8;">- -</span> Low / High scenarios</span>
      <span style="color: #636363; font-style: italic;">Dashed = projected</span>
    </div>
  `);
}
```

## Methodology Note

```js
if (hasData) {
  display(html`
    <blockquote style="border-left: 3px solid #ccc; padding: 0.5rem 1rem; color: #333; font-size: 0.9rem;">
      Utilisation-based projection: current service volume scaled by Stats NZ subnational
      population growth ratios (low / medium / high scenarios). Deferred demand factor applied
      where specified. Projections run in 5-year steps from 2023 baseline.
    </blockquote>
  `);
}
```

## Evidence-Based Leading Indicators

The following relationships are established in NZ health literature. These are qualitative commentary notes, not quantitative adjustments to the model:

| Signal | Indicator | Lag |
|---|---|---|
| GP access difficulty | ED presentation rate | ~3 months |
| Housing deprivation quintile | Child hospitalisation rate | Variable |
| Workforce vacancy rate | Median wait time growth | ~6 months |
| Age 85+ population share | Aged residential care demand | ~2 years |
| Amenable mortality | GP density (rural) | Long-term |

```js
const sourceFreshness = Array.from(await db.query(`SELECT slug, name, last_ingested_at FROM dim_data_source`));
display(dataFreshness(sourceFreshness));
```

---

*Source: Stats NZ subnational population projections + Health NZ service access data | CC BY 4.0 / Crown Copyright*

*Projections are estimates based on demographic change only. They do not account for policy changes, technology, or service model shifts.*
