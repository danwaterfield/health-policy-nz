---
title: GPS Scorecard

---

# GPS 2024–27 Accountability Scorecard

<p class="lead">Tracking New Zealand's Government Policy Statement on Health 2024–27 against available data.</p>

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

// Populate values from data — prose-first narrative
const scorecardData = GPS_PRIORITIES.map(p => {
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
  return { ...p, value, displayValue, source, tl };
});

// Narrative summary
{
  const total = scorecardData.length;
  const onTrack = scorecardData.filter(d => d.tl.label === "On track").length;
  const atRisk = scorecardData.filter(d => d.tl.label === "At risk").length;
  const offTrack = scorecardData.filter(d => d.tl.label === "Off track").length;
  const noData = scorecardData.filter(d => d.tl.label === "No data").length;
  const worst = scorecardData.find(d => d.tl.label === "Off track") ?? scorecardData.find(d => d.tl.label === "At risk");

  display(html`<div class="sidenote-container"><p>
    Of the five GPS priority areas, <span class="fig">${onTrack}</span> ${onTrack === 1 ? "is" : "are"} on track,
    <span class="fig fig-adverse">${atRisk + offTrack}</span> ${atRisk + offTrack === 1 ? "is" : "are"} at risk or off track,
    and <span class="fig">${noData}</span> lack public data entirely.${worst ? html` The furthest from target is <strong>${worst.metric}</strong> (${worst.displayValue}, target: ${worst.target}).` : ""}
  </p><span class="sidenote-number"></span><span class="sidenote">Traffic light thresholds: on track = meeting target; at risk = within 15% of target; off track = beyond 15%. Quality and Value metrics lack public data sources.</span></div>`);
}

// Minimal table — no coloured cards, just data
display(Inputs.table(scorecardData.map(d => ({
  Priority: d.priority,
  Metric: d.metric,
  Value: d.displayValue,
  Target: d.target,
  Status: `${d.tl.symbol} ${d.tl.label}`,
  Source: d.source,
})), {
  columns: ["Priority", "Metric", "Value", "Target", "Status", "Source"],
}));
```

```js
// (narrative summary is now inline above the table)
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
    x: {
      label: "Quarter",
      tickFormat: d => `${Math.floor(d)} Q${Math.round((d % 1) * 4) + 1}`,
    },
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
        x: d => d.year + (d.quarter - 1) * 0.25,
        y: "pct_within_target",
        stroke: "#1f77b4",
        strokeWidth: 2,
        tip: true,
      }),
      Plot.dot(edTrend, {
        x: d => d.year + (d.quarter - 1) * 0.25,
        y: "pct_within_target",
        fill: d => d.pct_within_target >= 95 ? "#2d8a4e" : "#c0392b",
        tip: true,
        title: d => `${d.year} Q${d.quarter}: ${d.pct_within_target?.toFixed(1)}%`,
      }),
    ],
  }));
  display(html`<p class="methodology">
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
    x: {
      label: "Quarter",
      tickFormat: d => `${Math.floor(d)} Q${Math.round((d % 1) * 4) + 1}`,
    },
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
        x: d => d.year + (d.quarter - 1) * 0.25,
        y: "median_wait_days",
        stroke: "#e5850b",
        strokeWidth: 2,
        tip: true,
      }),
      Plot.dot(fsaTrend, {
        x: d => d.year + (d.quarter - 1) * 0.25,
        y: "median_wait_days",
        fill: d => d.median_wait_days <= 42 ? "#2d8a4e" : "#c0392b",
        tip: true,
        title: d => `${d.year} Q${d.quarter}: ${d.median_wait_days?.toFixed(0)} days`,
      }),
    ],
  }));
  display(html`<p class="methodology">
    <span style="color: #2d8a4e;">●</span> Meeting target (≤42 days)
    <span style="color: #c0392b; margin-left: 1rem;">●</span> Exceeds target (&gt;42 days)
    <span style="color: #2d8a4e; margin-left: 1rem;">- -</span> 42-day target line
  </p>`);
}
```

<div class="aside">
<strong>Related:</strong> National targets can mask regional disparities. See <a href="./equity">Equity Gap Explorer</a> for how outcomes vary by ethnicity, and <a href="./workforce">Workforce</a> for the supply constraints behind these numbers.
</div>

## Data Freshness

```js
display(dataFreshness(sourceFreshness));
```

---

<p class="source-line">Source: Health New Zealand, NZHS, Medical Council NZ. Crown Copyright. Traffic light thresholds: on track (meeting target), at risk (within 15%), off track (beyond 15%).</p>
