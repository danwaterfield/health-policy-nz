---
title: Indicator Explorer
---

# Indicator Explorer

Multi-year trends for each health indicator, broken down by ethnicity.

```js
import {ciBar} from "./components/ci-bar.js";
import {exportButtons} from "./components/chart-export.js";
import {formatOrSuppress} from "./components/suppressed-cell.js";
import {dataFreshness} from "./components/data-freshness.js";
```

```js
const db = await DuckDBClient.of({
  fact_health_indicator: FileAttachment("data/fact_health_indicator.parquet"),
  dim_indicator: FileAttachment("data/dim_indicator.parquet"),
  dim_ethnicity: FileAttachment("data/dim_ethnicity.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
  dim_data_source: FileAttachment("data/dim_data_source.parquet"),
});
```

```js
const indicators = Array.from(await db.query(`
  SELECT DISTINCT i.id, i.name, i.slug, i.direction, i.unit
  FROM dim_indicator i
  JOIN fact_health_indicator fhi ON fhi.indicator_id = i.id
  ORDER BY i.name
`));

const ethnicities = Array.from(await db.query(`
  SELECT id, name FROM dim_ethnicity
  WHERE response_type = 'total_response'
  ORDER BY CASE name WHEN 'Total' THEN 0 WHEN 'Maori' THEN 1 WHEN 'Pacific' THEN 2 WHEN 'Asian' THEN 3 ELSE 4 END
`));

const regions = Array.from(await db.query(`
  SELECT id, name, level FROM dim_geography
  WHERE level IN ('national', 'health_region')
  ORDER BY CASE level WHEN 'national' THEN 0 ELSE 1 END, name
`));
```

```js
const selectedIndicator = view(Inputs.select(
  new Map(indicators.map(d => [d.name, d.id])),
  { label: "Indicator", value: indicators[0]?.id }
));

const selectedEthnicities = view(Inputs.checkbox(
  new Map(ethnicities.map(d => [d.name === "Maori" ? "Māori" : d.name, d.id])),
  { label: "Ethnicity", value: ethnicities.filter(d => ["Maori", "Pacific", "European/Other"].includes(d.name)).map(d => d.id) }
));

const selectedRegion = view(Inputs.select(
  new Map(regions.map(d => [`${d.level === "national" ? "★ " : ""}${d.name}`, d.id])),
  { label: "Region", value: regions.find(d => d.level === "national")?.id }
));
```

```js
const ind = indicators.find(d => d.id === selectedIndicator);

// Validate inputs against known values before interpolating into SQL
const knownIndicatorIds = indicators.map(d => d.id);
const knownRegionIds = regions.map(d => d.id);
const safeIndicator = knownIndicatorIds.includes(selectedIndicator) ? selectedIndicator : null;
const safeRegion = knownRegionIds.includes(selectedRegion) ? selectedRegion : null;

const data = (safeIndicator != null && safeRegion != null) ? Array.from(await db.query(`
  SELECT
    fhi.value,
    fhi.value_lower_ci,
    fhi.value_upper_ci,
    fhi.suppressed,
    e.name AS ethnicity,
    e.id AS ethnicity_id,
    t.year,
    g.name AS region
  FROM fact_health_indicator fhi
  JOIN dim_ethnicity e ON fhi.ethnicity_id = e.id
  JOIN dim_time t ON fhi.time_id = t.id
  JOIN dim_geography g ON fhi.geography_id = g.id
  WHERE fhi.indicator_id = ${safeIndicator}
    AND fhi.geography_id = ${safeRegion}
    AND e.response_type = 'total_response'
  ORDER BY t.year, e.name
`)) : [];

const filtered = data.filter(d => selectedEthnicities.includes(d.ethnicity_id));
const hasCI = filtered.some(d => d.value_lower_ci != null && d.value_upper_ci != null);
```

```js
// Computed narrative headline
{
  const valid = filtered.filter(d => !d.suppressed && d.value != null);
  if (valid.length > 1) {
    const years = [...new Set(valid.map(d => d.year))].sort();
    const earliest = years[0];
    const latest = years[years.length - 1];
    const eths = [...new Set(valid.map(d => d.ethnicity))];
    let bestEth = null, bestChange = 0, bestStart = 0, bestEnd = 0;
    for (const eth of eths) {
      const ethRows = valid.filter(d => d.ethnicity === eth);
      const startRow = ethRows.find(d => d.year === earliest);
      const endRow = ethRows.find(d => d.year === latest);
      if (startRow && endRow) {
        const change = endRow.value - startRow.value;
        if (Math.abs(change) > Math.abs(bestChange)) {
          bestEth = eth;
          bestChange = change;
          bestStart = startRow.value;
          bestEnd = endRow.value;
        }
      }
    }
    if (bestEth) {
      const displayName = ({"Maori": "Māori"})[bestEth] ?? bestEth;
      const dir = bestChange > 0 ? "increased" : "decreased";
      display(html`<div style="background: #f0f4f8; border-left: 4px solid #2563eb; padding: 1rem 1.25rem; margin: 1.5rem 0; border-radius: 4px; font-size: 1.05em; line-height: 1.6;">
        <strong>${ind?.name ?? "Indicator"}</strong> for <strong>${displayName}</strong> has ${dir} by <strong>${Math.abs(bestChange).toFixed(1)}</strong> percentage points since ${earliest}, from ${bestStart.toFixed(1)}% to ${bestEnd.toFixed(1)}%.
      </div>`);
    }
  }
}
```

## ${ind?.name ?? "—"} — Time Series

```js
const displayEthnicity = (name) => ({ "Maori": "Māori", "Pacific": "Pacific", "Asian": "Asian", "European/Other": "European/Other", "Total": "Total", "MELAA": "MELAA", "Other": "Other" })[name] ?? name;

if (filtered.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">No data for this selection.</p>`);
} else {
  // Wong colorblind-safe palette (Nat Methods 2011)
  const ethColors = {
    "Total": "#555555",
    "Maori": "#e69f00",
    "Pacific": "#56b4e9",
    "Asian": "#009e73",
    "European/Other": "#0072b2",
    "MELAA": "#d55e00",
    "Other": "#cc79a7",
  };

  const marks = [];

  // CI bands per ethnicity
  if (hasCI) {
    for (const eth of [...new Set(filtered.map(d => d.ethnicity))]) {
      const ethData = filtered.filter(d => d.ethnicity === eth && d.value_lower_ci != null);
      if (ethData.length > 0) {
        marks.push(Plot.areaY(ethData, {
          x: "year", y1: "value_lower_ci", y2: "value_upper_ci",
          fill: ethColors[eth] ?? "#636363", fillOpacity: 0.12,
        }));
      }
    }
  }

  // Lines
  marks.push(Plot.lineY(filtered.filter(d => !d.suppressed && d.value != null), {
    x: "year", y: "value", stroke: d => displayEthnicity(d.ethnicity),
    strokeWidth: 2, tip: true,
  }));

  // Points
  marks.push(Plot.dot(filtered.filter(d => !d.suppressed && d.value != null), {
    x: "year", y: "value", fill: d => displayEthnicity(d.ethnicity),
    title: d => `${displayEthnicity(d.ethnicity)} ${d.year}: ${d.value?.toFixed(1)}${ind?.unit ?? ""}`,
  }));

  // Suppressed markers — shown as tickmarks on x-axis with distinct styling
  const suppressed = filtered.filter(d => d.suppressed);
  if (suppressed.length > 0) {
    marks.push(Plot.tickX(suppressed, {
      x: "year",
      stroke: "#c0392b",
      strokeWidth: 2,
      strokeDasharray: "3,3",
      title: d => `${displayEthnicity(d.ethnicity)} ${d.year}: suppressed (sample size < 30)`,
    }));
    marks.push(Plot.text(suppressed, {
      x: "year",
      y: () => null,
      text: () => "S",
      dy: -8,
      fontSize: 9,
      fill: "#c0392b",
      textAnchor: "middle",
      frameAnchor: "bottom",
      title: d => `${displayEthnicity(d.ethnicity)} ${d.year}: suppressed (sample size < 30)`,
    }));
  }

  const timeSeriesPlot = Plot.plot({
    title: `${ind.name} by ethnicity`,
    subtitle: `${regions.find(d => d.id === selectedRegion)?.name ?? ""}${hasCI ? " · Shaded bands = 95% CI" : ""}`,
    marginLeft: 60,
    width,
    height: 400,
    color: {
      legend: true,
      domain: [...new Set(filtered.map(d => d.ethnicity))].map(displayEthnicity),
      range: [...new Set(filtered.map(d => d.ethnicity))].map(e => ethColors[e] ?? "#636363"),
    },
    y: { label: `${ind.name} (${ind.unit ?? "%"})` },
    x: { label: "Year", tickFormat: "d" },
    marks,
  });
  display(timeSeriesPlot);
  display(exportButtons(timeSeriesPlot, filtered, { filename: `${ind?.slug ?? "indicator"}-time-series` }));
}
```

## Regional Comparison — ${ind?.name ?? ""}

```js
// Latest year for this indicator across all regions
const regionData = safeIndicator != null ? Array.from(await db.query(`
  WITH latest AS (
    SELECT MAX(t.year) AS yr
    FROM fact_health_indicator fhi
    JOIN dim_time t ON fhi.time_id = t.id
    WHERE fhi.indicator_id = ${safeIndicator}
  )
  SELECT
    fhi.value,
    fhi.value_lower_ci,
    fhi.value_upper_ci,
    fhi.suppressed,
    g.name AS region,
    g.level,
    e.name AS ethnicity,
    t.year
  FROM fact_health_indicator fhi
  JOIN dim_geography g ON fhi.geography_id = g.id
  JOIN dim_ethnicity e ON fhi.ethnicity_id = e.id
  JOIN dim_time t ON fhi.time_id = t.id
  JOIN latest l ON t.year = l.yr
  WHERE fhi.indicator_id = ${safeIndicator}
    AND e.name = 'Total' AND e.response_type = 'total_response'
    AND fhi.suppressed = FALSE
    AND fhi.value IS NOT NULL
    AND g.level IN ('national', 'health_region')
  ORDER BY fhi.value DESC
`)) : [];

if (regionData.length > 1) {
  const natValue = regionData.find(d => d.level === "national")?.value;

  display(Plot.plot({
    title: `${ind.name} by region (${regionData[0]?.year}, Total population)`,
    subtitle: regionData.length > 1 ? `Range: ${Math.min(...regionData.map(d => d.value)).toFixed(1)}–${Math.max(...regionData.map(d => d.value)).toFixed(1)}${ind.unit ?? "%"}` : "",
    marginLeft: 220,
    width,
    height: Math.max(200, regionData.length * 28),
    x: { label: ind.unit ?? "%" },
    y: { domain: regionData.map(d => d.region) },
    marks: [
      natValue != null ? Plot.ruleX([natValue], {
        stroke: "#333", strokeDasharray: "4,4",
        title: `National average: ${natValue.toFixed(1)}`,
      }) : null,
      Plot.barX(regionData, {
        x: "value", y: "region",
        fill: d => d.level === "national" ? "#333" : "#4a90d9",
        title: d => `${d.region}: ${d.value?.toFixed(1)}${ind.unit ?? "%"}`,
      }),
      // CI whiskers
      regionData.some(d => d.value_lower_ci != null) ? Plot.link(regionData.filter(d => d.value_lower_ci != null), {
        x1: "value_lower_ci", x2: "value_upper_ci", y1: "region", y2: "region",
        stroke: "#333", strokeWidth: 1.5,
      }) : null,
      // CI end caps
      regionData.some(d => d.value_lower_ci != null) ? Plot.tickX(regionData.filter(d => d.value_lower_ci != null), {
        x: "value_lower_ci", y: "region", stroke: "#333", strokeWidth: 1.5,
      }) : null,
      regionData.some(d => d.value_upper_ci != null) ? Plot.tickX(regionData.filter(d => d.value_upper_ci != null), {
        x: "value_upper_ci", y: "region", stroke: "#333", strokeWidth: 1.5,
      }) : null,
    ].filter(Boolean),
  }));
} else {
  display(html`<p style="color: #636363; font-style: italic;">Only one region has data for this indicator.</p>`);
}
```

<details style="margin-top: 1.5rem;">
<summary style="cursor: pointer; font-weight: 600; color: #1e293b; font-size: 1em;">View data table</summary>

```js
if (filtered.length > 0) {
  display(Inputs.table(
    filtered.map(d => ({
      Year: String(d.year),
      Ethnicity: displayEthnicity(d.ethnicity),
      Value: d.suppressed ? "S*" : d.value?.toFixed(1) ?? "—",
      "Lower CI": d.suppressed ? "S" : d.value_lower_ci?.toFixed(1) ?? "—",
      "Upper CI": d.suppressed ? "S" : d.value_upper_ci?.toFixed(1) ?? "—",
      Suppressed: d.suppressed ? "Yes" : "",
    })),
    { sort: "Year", reverse: true }
  ));
  if (filtered.some(d => d.suppressed)) {
    display(html`<p style="font-size: 0.82em; color: #555; margin-top: 0.25rem;">
      <strong>S*</strong> = Suppressed: sample size too small (n &lt; 30) to report reliably. Value withheld to protect confidentiality.
    </p>`);
  }
  display(exportButtons(null, filtered.map(d => ({
    year: d.year, ethnicity: d.ethnicity, value: d.value,
    lower_ci: d.value_lower_ci, upper_ci: d.value_upper_ci,
    suppressed: d.suppressed, region: d.region,
  })), { filename: `${ind?.slug ?? "indicator"}-data` }));
}
```

</details>

```js
const sourceFreshness = Array.from(await db.query(`SELECT slug, name, last_ingested_at FROM dim_data_source`));
display(dataFreshness(sourceFreshness));
```

---

*Source: NZ Health Survey (NZHS) | Ministry of Health NZ | CC BY 4.0*
