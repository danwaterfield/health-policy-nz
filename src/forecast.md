---
title: Demand Forecast
---

# Demand Forecast

Projected health service demand under Stats NZ demographic scenarios.

```js
const db = await DuckDBClient.of({
  fact_demand_projection: FileAttachment("data/fact_demand_projection.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
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
// Query projection data for all scenarios
const projections = Array.from(await db.query(`
  SELECT
    fdp.scenario,
    fdp.projected_volume,
    fdp.capacity_gap,
    fdp.projection_basis,
    t.year
  FROM fact_demand_projection fdp
  JOIN dim_time t ON fdp.time_id = t.id
  WHERE fdp.service_type = '${selectedService}'
    AND fdp.geography_id = ${selectedGeo}
    AND fdp.projection_basis LIKE '%utilisation%'
  ORDER BY t.year, fdp.scenario
`));

const hasData = projections.length > 0;
```

## Demand Projections — ${selectedService?.toUpperCase()} Service

```js
if (!hasData) {
  display(html`
    <div style="padding: 2rem; background: #f5f5f5; border-radius: 8px; color: #333;">
      <p><strong>No projection data available</strong></p>
      <p>This will populate once you run the full pipeline with health targets seed data.</p>
      <pre>make pipeline && make copy-data</pre>
    </div>
  `);
} else {
  const baseline = projections.filter(d => d.scenario === "baseline");
  const high = projections.filter(d => d.scenario === "high");
  const low = projections.filter(d => d.scenario === "low");

  display(Plot.plot({
    title: `Projected demand — ${selectedService} service`,
    marginLeft: 80,
    width: 700,
    y: { label: "Projected volume" },
    x: { label: "Year" },
    marks: [
      // Uncertainty band (low to high)
      Plot.areaY(
        projections.filter(d => d.scenario !== "baseline"),
        Plot.groupX(
          { y1: "min", y2: "max" },
          { x: "year", y: "projected_volume", fill: "#1f77b4", fillOpacity: 0.15 }
        )
      ),
      // Scenario lines
      Plot.lineY(low, {
        x: "year", y: "projected_volume",
        stroke: "#aec7e8", strokeWidth: 1.5, strokeDasharray: "4,4",
        title: d => `Low scenario: ${d.projected_volume?.toFixed(0)}`,
      }),
      Plot.lineY(high, {
        x: "year", y: "projected_volume",
        stroke: "#aec7e8", strokeWidth: 1.5, strokeDasharray: "4,4",
        title: d => `High scenario: ${d.projected_volume?.toFixed(0)}`,
      }),
      // Baseline
      Plot.lineY(baseline, {
        x: "year", y: "projected_volume",
        stroke: "#1f77b4", strokeWidth: 2.5,
        title: d => `Baseline: ${d.projected_volume?.toFixed(0)}`,
      }),
      Plot.dot(baseline, {
        x: "year", y: "projected_volume",
        fill: "#1f77b4",
        symbol: "circle",
        title: d => `${d.year}: ${d.projected_volume?.toFixed(0)} (baseline)`,
      }),
    ],
  }));

  // Legend
  display(html`
    <div style="display: flex; gap: 1.5rem; font-size: 0.9rem; margin: 0.5rem 0 1rem;">
      <span><span style="color: #1f77b4; font-weight: bold;">—</span> Baseline</span>
      <span><span style="color: #aec7e8;">- -</span> Low / High scenarios</span>
      <span style="color: #999; font-style: italic;">Dashed = projected</span>
    </div>
  `);
}
```

## Methodology Note

```js
if (hasData && projections[0]?.projection_basis) {
  display(html`
    <blockquote style="border-left: 3px solid #ccc; padding: 0.5rem 1rem; color: #333; font-size: 0.9rem;">
      ${projections[0].projection_basis}
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

---

*Source: Stats NZ subnational population projections + Health NZ service access data | CC BY 4.0 / Crown Copyright*

*Projections are estimates based on demographic change only. They do not account for policy changes, technology, or service model shifts.*
