---
title: GPS Scorecard
---

# GPS 2024–27 Accountability Scorecard

New Zealand Government Policy Statement on Health 2024–27 priority areas.

```js
import {exportButtons} from "./components/chart-export.js";
```

```js
const db = await DuckDBClient.of({
  fact_service_access: FileAttachment("data/fact_service_access.parquet"),
  fact_health_indicator: FileAttachment("data/fact_health_indicator.parquet"),
  fact_workforce: FileAttachment("data/fact_workforce.parquet"),
  dim_indicator: FileAttachment("data/dim_indicator.parquet"),
  dim_data_source: FileAttachment("data/dim_data_source.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
  dim_ethnicity: FileAttachment("data/dim_ethnicity.parquet"),
});
```

```js
function trafficLight(value, threshold, direction) {
  if (value === null || threshold === null) return { color: "#999", label: "No data", symbol: "—" };
  const better = direction === "higher_better" ? value >= threshold : value <= threshold;
  const borderline = direction === "higher_better"
    ? (value >= threshold * 0.85 && value < threshold)
    : (value <= threshold * 1.15 && value > threshold);

  if (better) return { color: "#2d8a4e", label: "On track", symbol: "✓" };
  if (borderline) return { color: "#e5850b", label: "At risk", symbol: "⚠" };
  return { color: "#c0392b", label: "Off track", symbol: "✕" };
}
```

```js
// Fetch latest service access data (ED, FSA) for national level
const latestAccess = Array.from(await db.query(`
  SELECT
    fsa.service_type,
    fsa.pct_within_target,
    fsa.median_wait_days,
    t.year, t.quarter
  FROM fact_service_access fsa
  JOIN dim_time t ON fsa.time_id = t.id
  WHERE fsa.geography_id = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
  ORDER BY t.year DESC, t.quarter DESC NULLS LAST
`));

// Fetch latest unmet need for GP (Access priority) — national, Total ethnicity
const unmetNeed = Array.from(await db.query(`
  SELECT fhi.value, t.year
  FROM fact_health_indicator fhi
  JOIN dim_indicator i ON fhi.indicator_id = i.id
  JOIN dim_time t ON fhi.time_id = t.id
  JOIN dim_ethnicity e ON fhi.ethnicity_id = e.id
  WHERE i.slug = 'unmet_need_gp'
    AND fhi.geography_id = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
    AND e.name = 'Total' AND e.response_type = 'total_response'
    AND fhi.suppressed = FALSE
    AND fhi.value IS NOT NULL
  ORDER BY t.year DESC
  LIMIT 1
`));

// Fetch latest national nurse vacancy rate (Workforce priority)
const nurseVacancy = Array.from(await db.query(`
  SELECT fw.vacancy_rate, t.year
  FROM fact_workforce fw
  JOIN dim_time t ON fw.time_id = t.id
  WHERE fw.role_type = 'nurse'
    AND fw.geography_id = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
  ORDER BY t.year DESC
  LIMIT 1
`));

// Fetch latest data source timestamps
const sourceFreshness = Array.from(await db.query(`
  SELECT slug, name, last_ingested_at FROM dim_data_source
`));
```

```js
// GPS priority areas
const GPS_PRIORITIES = [
  {
    priority: "Access",
    metric: "% with unmet GP need due to cost",
    target: "< 10%",
    greenThreshold: 10,
    direction: "lower_better",
  },
  {
    priority: "Timeliness",
    metric: "ED within 6hrs / FSA median days",
    target: "> 95% / < 42 days",
    greenThreshold: 95,
    direction: "higher_better",
  },
  {
    priority: "Quality",
    metric: "Immunisation / Cancer treatment",
    target: "> 95% / > 85%",
    greenThreshold: 95,
    direction: "higher_better",
  },
  {
    priority: "Workforce",
    metric: "Nursing vacancy rate",
    target: "< 8%",
    greenThreshold: 8,
    direction: "lower_better",
  },
  {
    priority: "Value",
    metric: "Cost per weighted unit",
    target: "Data gap",
    greenThreshold: null,
    direction: null,
  },
];

// Populate values from data
const scorecardRows = GPS_PRIORITIES.map(p => {
  let value = null;
  let displayValue = "—";
  let source = "";

  if (p.priority === "Access") {
    const row = unmetNeed[0];
    if (row?.value != null) {
      value = row.value;
      displayValue = `${value.toFixed(1)}%`;
      source = `NZHS ${row.year}`;
    }
  } else if (p.priority === "Timeliness") {
    const edRow = latestAccess.find(d => d.service_type === "ed");
    if (edRow?.pct_within_target != null) {
      value = edRow.pct_within_target;
      displayValue = `${value.toFixed(1)}% within 6hrs`;
      source = edRow.quarter ? `Q${edRow.quarter} ${edRow.year}` : `${edRow.year}`;
    }
  } else if (p.priority === "Quality") {
    displayValue = "No data source";
    source = "Immunisation/cancer data not yet ingested";
  } else if (p.priority === "Workforce") {
    const row = nurseVacancy[0];
    if (row?.vacancy_rate != null) {
      value = row.vacancy_rate * 100;
      displayValue = `${value.toFixed(1)}%`;
      source = `${row.year}`;
    }
  } else if (p.priority === "Value") {
    displayValue = "No data source";
    source = "Cost data not publicly available";
  }

  const tl = trafficLight(value, p.greenThreshold, p.direction);

  return html`<tr style="border-bottom: 1px solid #eee;">
    <td><strong>${p.priority}</strong></td>
    <td>${p.metric}</td>
    <td style="font-family: monospace;">${p.target}</td>
    <td style="font-weight: 600;">${displayValue}</td>
    <td style="color: ${tl.color}; font-size: 1.3em; text-align: center; font-weight: bold;"
        title="${tl.label}">${tl.symbol}</td>
    <td style="color: ${tl.color}; font-weight: 500;">${tl.label}</td>
    <td style="color: #888; font-size: 0.85em;">${source}</td>
  </tr>`;
});

display(html`
  <table style="width: 100%; border-collapse: collapse; margin: 1rem 0;">
    <thead>
      <tr style="border-bottom: 2px solid #ccc; font-size: 0.9em;">
        <th style="text-align: left; padding: 0.5rem;">Priority</th>
        <th style="text-align: left; padding: 0.5rem;">Key Metric</th>
        <th style="text-align: left; padding: 0.5rem;">Target</th>
        <th style="text-align: left; padding: 0.5rem;">Latest</th>
        <th style="text-align: center; padding: 0.5rem;">Status</th>
        <th style="text-align: left; padding: 0.5rem;">Assessment</th>
        <th style="text-align: left; padding: 0.5rem;">Source</th>
      </tr>
    </thead>
    <tbody>
      ${scorecardRows}
    </tbody>
  </table>
`);
```

## ED Wait Times — Quarterly Trend

```js
const edTrend = Array.from(await db.query(`
  SELECT
    fsa.pct_within_target,
    fsa.volume_seen,
    t.year, t.quarter,
    t.period_label
  FROM fact_service_access fsa
  JOIN dim_time t ON fsa.time_id = t.id
  WHERE fsa.service_type = 'ed'
    AND fsa.geography_id = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
  ORDER BY t.year, t.quarter
`));

if (edTrend.length > 0) {
  display(Plot.plot({
    title: "ED 6-hour target — national",
    marginLeft: 60,
    width,
    y: {
      label: "% seen within 6 hours",
      domain: [75, 100],
    },
    marks: [
      Plot.ruleY([95], { stroke: "#2d8a4e", strokeDasharray: "4,4", title: "Target: 95%" }),
      Plot.lineY(edTrend, {
        x: d => `${d.year} Q${d.quarter}`,
        y: "pct_within_target",
        stroke: "#1f77b4",
        strokeWidth: 2,
        tip: true,
      }),
      Plot.dot(edTrend, {
        x: d => `${d.year} Q${d.quarter}`,
        y: "pct_within_target",
        fill: d => d.pct_within_target >= 95 ? "#2d8a4e" : "#c0392b",
        tip: true,
        title: d => `Q${d.quarter} ${d.year}: ${d.pct_within_target?.toFixed(1)}%`,
      }),
    ],
  }));
} else {
  display(html`<p style="color: #888; font-style: italic;">No ED time series data yet. Run the pipeline.</p>`);
}
```

## FSA Wait Times — Quarterly Trend

```js
const fsaTrend = Array.from(await db.query(`
  SELECT
    fsa.median_wait_days,
    t.year, t.quarter
  FROM fact_service_access fsa
  JOIN dim_time t ON fsa.time_id = t.id
  WHERE fsa.service_type = 'fsa'
    AND fsa.geography_id = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
  ORDER BY t.year, t.quarter
`));

if (fsaTrend.length > 0) {
  display(Plot.plot({
    title: "First Specialist Assessment — median wait days (national)",
    marginLeft: 60,
    width,
    y: { label: "Median wait (days)" },
    marks: [
      Plot.ruleY([42], { stroke: "#2d8a4e", strokeDasharray: "4,4", title: "Target: 42 days" }),
      Plot.lineY(fsaTrend, {
        x: d => `${d.year} Q${d.quarter}`,
        y: "median_wait_days",
        stroke: "#e5850b",
        strokeWidth: 2,
        tip: true,
      }),
      Plot.dot(fsaTrend, {
        x: d => `${d.year} Q${d.quarter}`,
        y: "median_wait_days",
        fill: d => d.median_wait_days <= 42 ? "#2d8a4e" : "#c0392b",
        tip: true,
      }),
    ],
  }));
}
```

## Data Freshness

```js
display(html`
  <div style="margin-top: 1rem; padding: 0.75rem 1rem; background: #f8f8f8; border-radius: 6px; font-size: 0.85em;">
    <strong>Data sources:</strong>
    ${sourceFreshness.map(s => {
      const age = s.last_ingested_at
        ? Math.floor((Date.now() - new Date(s.last_ingested_at).getTime()) / 86400000)
        : null;
      const color = age === null ? "#999" : age < 14 ? "#2d8a4e" : age < 90 ? "#e5850b" : "#c0392b";
      const label = age === null ? "never" : age === 0 ? "today" : `${age}d ago`;
      return html`<span style="margin-right: 1.5rem; white-space: nowrap;">
        <span style="color: ${color}; font-weight: 600;">${label}</span> ${s.name}
      </span>`;
    })}
  </div>
`);
```

---

*Source: Health New Zealand, NZHS, Medical Council NZ | Crown Copyright*

*Traffic light: ✓ On track (meeting target) · ⚠ At risk (within 15%) · ✕ Off track (beyond 15%)*
