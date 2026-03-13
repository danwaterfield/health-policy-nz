---
title: GPS Scorecard
---

# GPS 2024–27 Accountability Scorecard

New Zealand Government Policy Statement on Health 2024–27 priority areas.

```js
import {exportButtons} from "./components/chart-export.js";
import {dataFreshness} from "./components/data-freshness.js";
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
  if (value === null || threshold === null) return { color: "#636363", label: "No data", symbol: "—" };
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
const scorecardCards = GPS_PRIORITIES.map(p => {
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
      displayValue = `${value.toFixed(1)}%`;
      source = edRow.quarter ? `Q${edRow.quarter} ${edRow.year}` : `${edRow.year}`;
    }
  } else if (p.priority === "Quality") {
    displayValue = "No data";
    source = "Not yet ingested";
  } else if (p.priority === "Workforce") {
    const row = nurseVacancy[0];
    if (row?.vacancy_rate != null) {
      value = row.vacancy_rate * 100;
      displayValue = `${value.toFixed(1)}%`;
      source = `${row.year}`;
    }
  } else if (p.priority === "Value") {
    displayValue = "No data";
    source = "Not publicly available";
  }

  const tl = trafficLight(value, p.greenThreshold, p.direction);

  return html`
    <div style="
      border-radius: 12px;
      border: 1px solid #e0e0e0;
      border-left: 5px solid ${tl.color};
      padding: 1.25rem 1.5rem;
      background: white;
    ">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 0.75rem;">
        <div>
          <div style="font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.05em; color: #636363;">${p.priority}</div>
          <div style="font-size: 0.95em; font-weight: 500; margin-top: 0.15rem;">${p.metric}</div>
        </div>
        <div style="
          font-size: 1.8em;
          font-weight: bold;
          color: ${tl.color};
          line-height: 1;
        ">${tl.symbol}</div>
      </div>
      <div style="display: flex; justify-content: space-between; align-items: baseline;">
        <div>
          <div style="font-size: 1.6em; font-weight: 700; color: ${tl.color};">${displayValue}</div>
          <div style="font-size: 0.8em; color: #636363; margin-top: 0.15rem;">Target: ${p.target}</div>
        </div>
        <div style="text-align: right;">
          <div style="
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            font-size: 0.75em;
            font-weight: 600;
            background: ${tl.color}18;
            color: ${tl.color};
          ">${tl.label}</div>
          <div style="font-size: 0.75em; color: #636363; margin-top: 0.25rem;">${source}</div>
        </div>
      </div>
    </div>
  `;
});

display(html`
  <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 1rem; margin: 1.5rem 0;">
    ${scorecardCards}
  </div>
`);
```

```js
// Computed scorecard narrative headline
{
  const statuses = GPS_PRIORITIES.map(p => {
    let value = null;
    if (p.priority === "Access") {
      const row = unmetNeed[0];
      if (row?.value != null) value = row.value;
    } else if (p.priority === "Timeliness") {
      const edRow = latestAccess.find(d => d.service_type === "ed");
      if (edRow?.pct_within_target != null) value = edRow.pct_within_target;
    } else if (p.priority === "Workforce") {
      const row = nurseVacancy[0];
      if (row?.vacancy_rate != null) value = row.vacancy_rate * 100;
    }
    const tl = trafficLight(value, p.greenThreshold, p.direction);
    return { priority: p.priority, metric: p.metric, status: tl.label, value };
  });

  const total = statuses.length;
  const onTrack = statuses.filter(d => d.status === "On track").length;
  const atRisk = statuses.filter(d => d.status === "At risk").length;
  const offTrack = statuses.filter(d => d.status === "Off track").length;
  const noData = statuses.filter(d => d.status === "No data").length;

  // Find the worst performing metric (off track first, then at risk)
  const worst = statuses.find(d => d.status === "Off track") ?? statuses.find(d => d.status === "At risk");
  const summaryStatus = offTrack > 0 ? "off track" : atRisk > 0 ? "at risk" : "on track";

  const parts = [];
  if (onTrack > 0) parts.push(`${onTrack} on track`);
  if (atRisk > 0) parts.push(`${atRisk} at risk`);
  if (offTrack > 0) parts.push(`${offTrack} off track`);
  if (noData > 0) parts.push(`${noData} with no data`);

  display(html`<div style="background: #f0f4f8; border-left: 4px solid #2563eb; padding: 1rem 1.25rem; margin: 1.5rem 0; border-radius: 4px; font-size: 1.05em; line-height: 1.6;">
    <strong>${parts.join(", ")}</strong> of ${total} GPS targets.${worst ? html` <strong>${worst.metric}</strong> is the furthest from target.` : ""}
  </div>`);
}
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
      Plot.ruleY([95], { stroke: "#2d8a4e", strokeDasharray: "4,4" }),
      Plot.text([{ label: "Target: 95%" }], {
        frameAnchor: "right",
        dy: -10,
        text: "label",
        fontSize: 10,
        fill: "#2d8a4e",
      }),
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
  display(html`<p style="font-size: 0.82em; color: #555; margin-top: 0.25rem;">
    <span style="color: #2d8a4e;">●</span> Meeting target (≥95%)
    <span style="color: #c0392b; margin-left: 1rem;">●</span> Below target (&lt;95%)
    <span style="color: #2d8a4e; margin-left: 1rem;">- -</span> 95% target line
  </p>`);
} else {
  display(html`<p style="color: #636363; font-style: italic;">No ED time series data available yet.</p>`);
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
      Plot.ruleY([42], { stroke: "#2d8a4e", strokeDasharray: "4,4" }),
      Plot.text([{ label: "Target: 42 days" }], {
        frameAnchor: "right",
        dy: -10,
        text: "label",
        fontSize: 10,
        fill: "#2d8a4e",
      }),
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
        title: d => `Q${d.quarter} ${d.year}: ${d.median_wait_days?.toFixed(0)} days`,
      }),
    ],
  }));
  display(html`<p style="font-size: 0.82em; color: #555; margin-top: 0.25rem;">
    <span style="color: #2d8a4e;">●</span> Meeting target (≤42 days)
    <span style="color: #c0392b; margin-left: 1rem;">●</span> Exceeds target (&gt;42 days)
    <span style="color: #2d8a4e; margin-left: 1rem;">- -</span> 42-day target line
  </p>`);
}
```

<div style="background: #f8f4ff; border-left: 4px solid #7c3aed; padding: 1rem 1.25rem; margin: 1.5rem 0; border-radius: 4px;">
<strong>Related:</strong> National targets can mask regional disparities. See <a href="./equity">Equity Gap Explorer</a> for how outcomes vary by ethnicity, and <a href="./workforce">Workforce</a> for the supply constraints behind these numbers.
</div>

## Data Freshness

```js
display(dataFreshness(sourceFreshness));
```

---

*Source: Health New Zealand, NZHS, Medical Council NZ | Crown Copyright*

*Traffic light: ✓ On track (meeting target) · ⚠ At risk (within 15%) · ✕ Off track (beyond 15%)*
