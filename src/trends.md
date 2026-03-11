---
title: Pandemic Break Analysis
---

# Did COVID Change the Trajectory of Inequity?

Comparing the *rate of change* of equity gaps before and after the pandemic — not just levels, but whether the gap was widening or narrowing and at what speed.

```js
import {dataFreshness} from "./components/data-freshness.js";
```

```js
const db = await DuckDBClient.of({
  equity_gap:          FileAttachment("data/equity_gap.parquet"),
  dim_indicator:       FileAttachment("data/dim_indicator.parquet"),
  dim_ethnicity:       FileAttachment("data/dim_ethnicity.parquet"),
  dim_geography:       FileAttachment("data/dim_geography.parquet"),
  dim_time:            FileAttachment("data/dim_time.parquet"),
  fact_policy_events:  FileAttachment("data/fact_policy_events.parquet"),
  dim_data_source:     FileAttachment("data/dim_data_source.parquet"),
});
```


```js
// Full annual time series for all national + Māori/Pacific gaps (excluding COVID years from regression but showing them)
const allYears = Array.from(await db.query(`
  SELECT
    t.year,
    i.name  AS indicator,
    e.name  AS ethnicity,
    CASE eg.gap_direction
      WHEN 'adverse'    THEN  ABS(eg.absolute_gap)
      WHEN 'favourable' THEN -ABS(eg.absolute_gap)
      ELSE 0
    END AS severity,
    eg.gap_direction
  FROM equity_gap eg
  JOIN dim_time     t ON eg.time_id     = t.id
  JOIN dim_geography g ON eg.geography_id = g.id
  JOIN dim_indicator i ON eg.indicator_id = i.id
  JOIN dim_ethnicity e ON eg.target_ethnicity_id = e.id
  WHERE g.level = 'national'
    AND e.name IN ('Maori', 'Pacific')
  ORDER BY i.name, e.name, t.year
`));

// Policy turning points for annotation
const policyEvents = Array.from(await db.query(`
  SELECT
    YEAR(date::DATE) AS year,
    title,
    category
  FROM fact_policy_events
  WHERE tags LIKE '%turning_point%'
    AND YEAR(date::DATE) BETWEEN 2010 AND 2026
  ORDER BY date
`));
```

```js
// Helper: linear fit y = m*x + b for a set of {x, y} points
function linFit(pts) {
  const n = pts.length;
  if (n < 2) return null;
  const mx = pts.reduce((s, p) => s + p.x, 0) / n;
  const my = pts.reduce((s, p) => s + p.y, 0) / n;
  const ss = pts.reduce((s, p) => s + (p.x - mx) ** 2, 0);
  if (ss === 0) return null;
  const m  = pts.reduce((s, p) => s + (p.x - mx) * (p.y - my), 0) / ss;
  const b  = my - m * mx;
  return { m, b, predict: x => m * x + b };
}

// Worsened = slope became more positive (gap widening faster, or narrowing slower)
const worsened = d => d.slope_change > 0;

// Compute pre/post slopes in JS from allYears (avoids REGR_SLOPE in DuckDB-WASM)
const slopeData = (() => {
  // Group by indicator × ethnicity
  const groups = new Map();
  for (const row of allYears) {
    const key = `${row.indicator}||${row.ethnicity}`;
    if (!groups.has(key)) groups.set(key, { indicator: row.indicator, ethnicity: row.ethnicity, rows: [] });
    groups.get(key).rows.push(row);
  }

  const result = [];
  for (const [, g] of groups) {
    const prePts  = g.rows.filter(r => r.year >= 2011 && r.year <= 2019).map(r => ({ x: r.year, y: r.severity }));
    const postPts = g.rows.filter(r => r.year >= 2023).map(r => ({ x: r.year, y: r.severity }));
    if (prePts.length < 3 || postPts.length < 2) continue;

    const pre  = linFit(prePts);
    const post = linFit(postPts);
    if (!pre || !post) continue;

    const preMean  = prePts.reduce((s, p) => s + p.y, 0) / prePts.length;
    const postMean = postPts.reduce((s, p) => s + p.y, 0) / postPts.length;

    result.push({
      indicator:    g.indicator,
      ethnicity:    g.ethnicity,
      pre_slope:    pre.m,
      post_slope:   post.m,
      slope_change: post.m - pre.m,
      pre_mean:     preMean,
      post_mean:    postMean,
      level_change: postMean - preMean,
      pre_n:        prePts.length,
      post_n:       postPts.length,
    });
  }

  return result.sort((a, b) => Math.abs(b.slope_change) - Math.abs(a.slope_change));
})();
```

```js
display(html`
  <div style="
    border-left: 4px solid #666;
    background: #f7f7f7;
    border-radius: 0 6px 6px 0;
    padding: 0.75rem 1rem;
    margin-bottom: 1.5rem;
    font-size: 0.85em;
    color: #333;
  ">
    <strong>Methodological note</strong> — Pre-COVID period: 2011–2019 (9 annual data points).
    Post-COVID period: 2023–2024 (2 points only). COVID years 2020–2022 are excluded from both
    regressions as the NZHS methodology notes reduced participation and service disruption make
    those years non-comparable. <strong>Post-COVID slopes are based on two points — they describe
    observed direction, not a stable trend.</strong> Treat slope magnitudes as indicative;
    treat sign (widening vs. narrowing) as the primary finding.
  </div>
`);
```

## Slope Change — Which Indicators Shifted Most?

Each row is an indicator × ethnicity pair. The pre-COVID annual change rate is compared to the post-COVID annual change rate. **Positive slope change = the gap is now worsening faster (or improving more slowly) than before the pandemic.**

```js
if (slopeData.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">No slope data available — need at least 3 pre-COVID and 2 post-COVID data points per indicator.</p>`);
} else {
  const displayEthnicity = (name) => ({ "Maori": "Māori", "Pacific": "Pacific" })[name] ?? name;
  const sorted = [...slopeData].sort((a, b) => b.slope_change - a.slope_change);

  display(Plot.plot({
    title: "Annual rate of change in equity gap: pre-COVID (2011–19) vs post-COVID (2023–24)",
    subtitle: "Positive = gap worsening faster after COVID · Negative = gap narrowing faster after COVID",
    marginLeft: 240,
    marginRight: 80,
    width,
    height: Math.max(300, sorted.length * 26),
    x: {
      label: "Annual slope change (pp/year)",
      zero: true,
    },
    y: {
      domain: sorted.map(d => `${d.indicator} — ${displayEthnicity(d.ethnicity)}`),
      label: null,
    },
    marks: [
      Plot.ruleX([0], { stroke: "#636363" }),

      // Connecting line between pre and post slope
      Plot.link(sorted, {
        x1: "pre_slope",
        x2: "post_slope",
        y1: d => `${d.indicator} — ${displayEthnicity(d.ethnicity)}`,
        y2: d => `${d.indicator} — ${displayEthnicity(d.ethnicity)}`,
        stroke: d => worsened(d) ? "#c0392b" : "#4575b4",
        strokeWidth: 1.5,
        strokeOpacity: 0.6,
      }),

      // Pre-COVID dot (open circle)
      Plot.dot(sorted, {
        x: "pre_slope",
        y: d => `${d.indicator} — ${displayEthnicity(d.ethnicity)}`,
        fill: "white",
        stroke: "#555",
        strokeWidth: 1.5,
        r: 5,
        title: d => `${d.indicator} — ${d.ethnicity}\nPre-COVID slope: ${d.pre_slope >= 0 ? "+" : ""}${d.pre_slope?.toFixed(2)} pp/yr`,
      }),

      // Post-COVID dot (filled)
      Plot.dot(sorted, {
        x: "post_slope",
        y: d => `${d.indicator} — ${displayEthnicity(d.ethnicity)}`,
        fill: d => worsened(d) ? "#c0392b" : "#4575b4",
        r: 5,
        title: d => `${d.indicator} — ${d.ethnicity}\nPost-COVID slope: ${d.post_slope >= 0 ? "+" : ""}${d.post_slope?.toFixed(2)} pp/yr\nChange: ${d.slope_change >= 0 ? "+" : ""}${d.slope_change?.toFixed(2)} pp/yr`,
      }),

      // Slope change label on right
      Plot.text(sorted, {
        x: d => Math.max(d.pre_slope, d.post_slope),
        y: d => `${d.indicator} — ${displayEthnicity(d.ethnicity)}`,
        text: d => `${d.slope_change >= 0 ? "+" : ""}${d.slope_change?.toFixed(2)}`,
        dx: 8,
        textAnchor: "start",
        fontSize: 10,
        fill: d => worsened(d) ? "#c0392b" : "#4575b4",
        fontWeight: "600",
      }),
    ],
  }));

  display(html`<p style="font-size: 0.82em; color: #555; margin-top: 0.4rem;">
    Open circle = pre-COVID slope (2011–19) · Filled circle = post-COVID slope (2023–24) ·
    Line colour = direction of change. Units: percentage points per year.
  </p>`);
}
```

## Top Movers — Full Time Series

Indicators where the trajectory changed most, showing all years including the COVID period (shaded).

```js
{
  const topN = 6;
  const topIndicators = [...new Set(
    [...slopeData]
      .sort((a, b) => Math.abs(b.slope_change) - Math.abs(a.slope_change))
      .slice(0, topN)
      .map(d => d.indicator + "||" + d.ethnicity)
  )];

  if (topIndicators.length === 0) {
    display(html`<p style="color: #636363; font-style: italic;">Insufficient data for time series.</p>`);
  } else {
    const plots = topIndicators.map(key => {
      const [indicator, ethnicity] = key.split("||");
      const rows = allYears.filter(d => d.indicator === indicator && d.ethnicity === ethnicity);
      if (rows.length < 3) return null;

      // Compute trend lines
      const prePts  = rows.filter(d => d.year >= 2011 && d.year <= 2019).map(d => ({ x: d.year, y: d.severity }));
      const postPts = rows.filter(d => d.year >= 2023).map(d => ({ x: d.year, y: d.severity }));
      const preFit  = linFit(prePts);
      const postFit = linFit(postPts);

      const xMin = Math.min(...rows.map(d => d.year));
      const xMax = Math.max(...rows.map(d => d.year));
      const yExt = rows.map(d => d.severity);
      const yMin = Math.min(...yExt);
      const yMax = Math.max(...yExt);
      const yPad = (yMax - yMin) * 0.15 || 1;

      // Pre-trend line extended to 2022 (to show where it would have gone)
      const preLine = preFit
        ? [{ year: 2011, sev: preFit.predict(2011) }, { year: 2024, sev: preFit.predict(2024) }]
        : [];

      // Post-trend line (2023-2024)
      const postLine = postFit
        ? [{ year: 2023, sev: postFit.predict(2023) }, { year: 2024, sev: postFit.predict(2024) }]
        : [];

      const meta = slopeData.find(d => d.indicator === indicator && d.ethnicity === ethnicity);
      const dir  = meta ? (worsened(meta) ? "worsened" : "improved") : "";
      const col  = meta ? (worsened(meta) ? "#c0392b" : "#4575b4") : "#636363";

      const displayEthnicity = (name) => ({ "Maori": "Māori", "Pacific": "Pacific" })[name] ?? name;
      const plotWidth = Math.min(Math.floor((width - 40) / 2), 380);

      return Plot.plot({
        title: `${indicator} — ${displayEthnicity(ethnicity)}`,
        subtitle: meta
          ? `Slope: pre ${meta.pre_slope >= 0 ? "+" : ""}${meta.pre_slope?.toFixed(2)} → post ${meta.post_slope >= 0 ? "+" : ""}${meta.post_slope?.toFixed(2)} pp/yr (${dir})`
          : "",
        width: plotWidth,
        height: 220,
        marginRight: 10,
        x: { label: "Year", tickFormat: d => String(d) },
        y: { label: "Gap severity (pp)", domain: [yMin - yPad, yMax + yPad] },
        marks: [
          // COVID shading
          Plot.rectX(
            [{ x1: 2019.5, x2: 2022.5 }],
            { x1: "x1", x2: "x2", y1: yMin - yPad * 2, y2: yMax + yPad * 2, fill: "#f0f0f0" }
          ),
          Plot.text([{ year: 2021, label: "COVID" }], {
            x: "year", y: yMax + yPad * 0.5,
            text: "label", fontSize: 9, fill: "#bbb", textAnchor: "middle",
          }),

          // Policy turning points
          Plot.ruleX(
            policyEvents.filter(e => e.year >= xMin && e.year <= xMax),
            {
              x: "year",
              stroke: d => d.category === "repeal" ? "#e74c3c" : "#9b59b6",
              strokeWidth: 1,
              strokeDasharray: "2,4",
              title: d => d.title,
            }
          ),

          // Zero line
          Plot.ruleY([0], { stroke: "#ddd" }),

          // Actual data points
          Plot.lineY(rows, {
            x: "year", y: "severity",
            stroke: "#636363", strokeWidth: 1,
          }),
          Plot.dot(rows, {
            x: "year", y: "severity",
            fill: d => d.year >= 2020 && d.year <= 2022 ? "#ccc" : col,
            r: 3,
            title: d => `${d.year}: ${d.severity >= 0 ? "+" : ""}${d.severity?.toFixed(1)} pp (${d.gap_direction})`,
          }),

          // Pre-COVID trend extrapolated (dashed)
          ...(preLine.length > 0 ? [
            Plot.lineY(preLine, {
              x: "year", y: "sev",
              stroke: "#aaa", strokeWidth: 1.5, strokeDasharray: "5,4",
            }),
          ] : []),

          // Post-COVID trend (solid, coloured)
          ...(postLine.length > 0 ? [
            Plot.lineY(postLine, {
              x: "year", y: "sev",
              stroke: col, strokeWidth: 2.5,
            }),
          ] : []),
        ],
      });
    }).filter(Boolean);

    // Render in a 2-column grid
    display(html`
      <div style="display: flex; flex-wrap: wrap; gap: 1.5rem; margin: 1rem 0;">
        ${plots.map(p => html`<div>${p}</div>`)}
      </div>
    `);

    display(html`<p style="font-size: 0.82em; color: #555; margin-top: 0.25rem;">
      Grey shading = COVID period (2020–22), excluded from regressions.
      Dashed grey line = pre-COVID trend extrapolated forward.
      Coloured line = post-COVID observed trend.
      <span style="color: #c0392b;">Red</span> = worsened trajectory. <span style="color: #4575b4;">Blue</span> = improved.
    </p>`);
  }
}
```

## Summary Table

```js
if (slopeData.length > 0) {
  const worsenedCount  = slopeData.filter(worsened).length;
  const improvedCount  = slopeData.filter(d => !worsened(d)).length;
  const biggestWorsen  = [...slopeData].filter(worsened).sort((a, b) => b.slope_change - a.slope_change)[0];
  const biggestImprove = [...slopeData].filter(d => !worsened(d)).sort((a, b) => a.slope_change - b.slope_change)[0];

  display(html`
    <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; margin: 1rem 0;">
      <div style="padding: 0.75rem 1.25rem; background: #fdf2f2; border: 1px solid #e8a8a8; border-radius: 6px; color: #222;">
        <strong style="color: #c0392b;">${worsenedCount}</strong> indicator–ethnicity pairs
        worsened trajectory post-COVID
        ${biggestWorsen ? html`<br><small style="color: #555;">Largest: ${biggestWorsen.indicator} (${biggestWorsen.ethnicity}), +${biggestWorsen.slope_change?.toFixed(2)} pp/yr</small>` : ""}
      </div>
      <div style="padding: 0.75rem 1.25rem; background: #f0f9f4; border: 1px solid #90d0aa; border-radius: 6px; color: #222;">
        <strong style="color: #2d8a4e;">${improvedCount}</strong> indicator–ethnicity pairs
        improved trajectory post-COVID
        ${biggestImprove ? html`<br><small style="color: #555;">Largest: ${biggestImprove.indicator} (${biggestImprove.ethnicity}), ${biggestImprove.slope_change?.toFixed(2)} pp/yr</small>` : ""}
      </div>
    </div>
  `);

  display(Inputs.table(
    [...slopeData].sort((a, b) => b.slope_change - a.slope_change),
    {
      columns: ["indicator", "ethnicity", "pre_slope", "post_slope", "slope_change", "pre_mean", "post_mean", "level_change"],
      header: {
        indicator:    "Indicator",
        ethnicity:    "Ethnicity",
        pre_slope:    "Pre slope (pp/yr)",
        post_slope:   "Post slope (pp/yr)",
        slope_change: "Slope change",
        pre_mean:     "Pre avg gap (pp)",
        post_mean:    "Post avg gap (pp)",
        level_change: "Level change (pp)",
      },
      format: {
        pre_slope:    d => (d >= 0 ? "+" : "") + d?.toFixed(2),
        post_slope:   d => (d >= 0 ? "+" : "") + d?.toFixed(2),
        slope_change: d => (d >= 0 ? "+" : "") + d?.toFixed(2),
        pre_mean:     d => d?.toFixed(1),
        post_mean:    d => d?.toFixed(1),
        level_change: d => (d >= 0 ? "+" : "") + d?.toFixed(1),
      },
    }
  ));
}
```

```js
const sourceFreshness = Array.from(await db.query(`SELECT slug, name, last_ingested_at FROM dim_data_source`));
display(dataFreshness(sourceFreshness));
```

---

*Source: NZ Health Survey (Ministry of Health) 2011–2024, via NZHS Annual Data Explorer | CC BY 4.0*

*Pre-COVID regression: 2011–2019 (n=9). Post-COVID regression: 2023–2024 (n=2). COVID years 2020–2022 excluded. Slope = OLS coefficient (pp/year). Severity = signed gap magnitude, positive = worse for Māori/Pacific. Analysis is descriptive — statistical significance of slope change is not assessable with 2 post-COVID observations.*
