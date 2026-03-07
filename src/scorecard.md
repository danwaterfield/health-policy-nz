---
title: GPS Scorecard
---

# GPS 2024–27 Accountability Scorecard

New Zealand Government Policy Statement on Health 2024–27 priority areas.

```js
const db = await DuckDBClient.of({
  fact_service_access: FileAttachment("data/fact_service_access.parquet"),
  dim_indicator: FileAttachment("data/dim_indicator.parquet"),
  dim_data_source: FileAttachment("data/dim_data_source.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
});
```

```js
// GPS priority areas and rules
const GPS_PRIORITIES = [
  {
    priority: "Access",
    indicators: ["Unmet Need for GP"],
    metric: "% with unmet GP need",
    target: "< 10%",
    greenThreshold: 10,
    direction: "lower_better",
    icon: "🏥",
  },
  {
    priority: "Timeliness",
    indicators: ["ED 6-Hour Target", "First Specialist Assessment Wait Days"],
    metric: "ED within 6hrs / FSA median days",
    target: "> 95% / < 42 days",
    greenThreshold: 95,
    direction: "higher_better",
    icon: "⏱",
  },
  {
    priority: "Quality",
    indicators: ["Childhood Immunisation Rate", "Cancer Treatment 62-Day"],
    metric: "Immunisation / Cancer treatment",
    target: "> 95% / > 85%",
    greenThreshold: 95,
    direction: "higher_better",
    icon: "✓",
  },
  {
    priority: "Workforce",
    indicators: ["Nurse Vacancy Rate"],
    metric: "Nursing vacancy rate",
    target: "< 8%",
    greenThreshold: 8,
    direction: "lower_better",
    icon: "👩‍⚕️",
  },
  {
    priority: "Value",
    indicators: [],
    metric: "Cost per weighted unit",
    target: "Data gap",
    greenThreshold: null,
    direction: null,
    icon: "$",
  },
];

function trafficLight(value, threshold, direction) {
  if (value === null || threshold === null) return { color: "#999", label: "No data", symbol: "●" };
  const better = direction === "higher_better" ? value >= threshold : value <= threshold;
  const borderline = direction === "higher_better"
    ? (value >= threshold * 0.85 && value < threshold)
    : (value <= threshold * 1.15 && value > threshold);

  if (better) return { color: "#2d8a4e", label: "On track", symbol: "●" };
  if (borderline) return { color: "#e5850b", label: "At risk", symbol: "●" };
  return { color: "#c0392b", label: "Off track", symbol: "●" };
}
```

```js
// Fetch latest service access data for national level
const latestAccess = Array.from(await db.query(`
  SELECT
    fsa.service_type,
    fsa.pct_within_target,
    fsa.median_wait_days,
    t.year, t.quarter
  FROM fact_service_access fsa
  JOIN dim_time t ON fsa.time_id = t.id
  WHERE fsa.geography_id = 1
  ORDER BY t.year DESC, t.quarter DESC NULLS LAST
`));
```

```js
// Render scorecard
const scorecardRows = GPS_PRIORITIES.map(p => {
  let value = null;
  let displayValue = "—";

  if (p.priority === "Timeliness") {
    const edRow = latestAccess.find(d => d.service_type === "ed");
    if (edRow?.pct_within_target) {
      value = edRow.pct_within_target;
      displayValue = `${value.toFixed(1)}% within 6hrs`;
    }
  } else if (p.priority === "Workforce") {
    displayValue = "See Workforce page";
  }

  const tl = trafficLight(value, p.greenThreshold, p.direction);

  return html`<tr>
    <td style="font-size: 1.4em; text-align: center;">${p.icon}</td>
    <td><strong>${p.priority}</strong></td>
    <td>${p.metric}</td>
    <td>${p.target}</td>
    <td>${displayValue}</td>
    <td style="color: ${tl.color}; font-size: 1.2em; text-align: center;"
        title="${tl.label}">${tl.symbol}</td>
    <td style="color: ${tl.color};">${tl.label}</td>
  </tr>`;
});

display(html`
  <table style="width: 100%; border-collapse: collapse; margin: 1rem 0;">
    <thead>
      <tr style="border-bottom: 2px solid #ccc;">
        <th></th>
        <th>Priority Area</th>
        <th>Key Metric</th>
        <th>Target</th>
        <th>Latest Value</th>
        <th>Status</th>
        <th>Assessment</th>
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
    AND fsa.geography_id = 1
  ORDER BY t.year, t.quarter
`));

if (edTrend.length > 0) {
  display(Plot.plot({
    title: "ED 6-hour target — national",
    marginLeft: 60,
    width: 700,
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
      }),
      Plot.dot(edTrend, {
        x: d => `${d.year} Q${d.quarter}`,
        y: "pct_within_target",
        fill: d => d.pct_within_target >= 95 ? "#2d8a4e" : "#c0392b",
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
    AND fsa.geography_id = 1
  ORDER BY t.year, t.quarter
`));

if (fsaTrend.length > 0) {
  display(Plot.plot({
    title: "First Specialist Assessment — median wait days (national)",
    marginLeft: 60,
    width: 700,
    y: { label: "Median wait (days)" },
    marks: [
      Plot.ruleY([42], { stroke: "#2d8a4e", strokeDasharray: "4,4", title: "Target: 42 days" }),
      Plot.lineY(fsaTrend, {
        x: d => `${d.year} Q${d.quarter}`,
        y: "median_wait_days",
        stroke: "#e5850b",
        strokeWidth: 2,
      }),
      Plot.dot(fsaTrend, {
        x: d => `${d.year} Q${d.quarter}`,
        y: "median_wait_days",
        fill: d => d.median_wait_days <= 42 ? "#2d8a4e" : "#c0392b",
      }),
    ],
  }));
}
```

---

*Source: Health New Zealand Quarterly Health Targets | Crown Copyright*

*Traffic light rules: On track = meeting target; At risk = within 15% of target; Off track = beyond 15% from target.*
