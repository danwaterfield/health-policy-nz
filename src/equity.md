---
title: Equity Gap Explorer
---

# Equity Gap Explorer

Comparing health indicator values for Māori and Pacific peoples against the European/Other reference population, at national and regional level.

```js
import {choropleth} from "./components/choropleth.js";
import {exportButtons} from "./components/chart-export.js";
import {formatOrSuppress} from "./components/suppressed-cell.js";
import {dataFreshness} from "./components/data-freshness.js";
const nzTopo = await FileAttachment("data/nz-health-regions.json").json();
```

```js
const db = await DuckDBClient.of({
  equity_gap: FileAttachment("data/equity_gap.parquet"),
  fact_health_indicator: FileAttachment("data/fact_health_indicator.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
  dim_indicator: FileAttachment("data/dim_indicator.parquet"),
  dim_ethnicity: FileAttachment("data/dim_ethnicity.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
  fact_nzdep: FileAttachment("data/fact_nzdep.parquet"),
  fact_bias_estimates: FileAttachment("data/fact_bias_estimates.parquet"),
  fact_life_tables: FileAttachment("data/fact_life_tables.parquet"),
  fact_corrections: FileAttachment("data/fact_corrections.parquet"),
  fact_policy_events: FileAttachment("data/fact_policy_events.parquet"),
  dim_data_source: FileAttachment("data/dim_data_source.parquet"),
});
```

```js
// Load dimension data for selectors
const indicators = Array.from(await db.query(`
  SELECT id, name, slug, direction, unit FROM dim_indicator ORDER BY name
`));

const ethnicities = Array.from(await db.query(`
  SELECT id, name FROM dim_ethnicity
  WHERE name IN ('Maori', 'Pacific', 'Asian') AND response_type = 'total_response'
  ORDER BY name
`));
```

```js
// Controls
const indicatorId = view(Inputs.select(
  new Map(indicators.map(d => [d.name, d.id])),
  { label: "Indicator", value: indicators[0]?.id }
));

const selectedEthnicities = view(Inputs.checkbox(
  new Map(ethnicities.map(d => [d.name === "Maori" ? "Māori" : d.name, d.id])),
  { label: "Ethnicity", value: ethnicities.map(d => d.id) }
));

// Validate inputs against known values before SQL interpolation
const knownIndicatorIds = new Set(indicators.map(d => d.id));
const knownEthnicityIds = new Set(ethnicities.map(d => d.id));
```

```js
// Validate indicator — must come from known set
const safeIndicatorId = knownIndicatorIds.has(indicatorId) ? indicatorId : null;
const safeEthnicities = selectedEthnicities.filter(id => knownEthnicityIds.has(id));

// Latest year for the selected indicator
const latestYear = safeIndicatorId != null ? (Array.from(await db.query(`
  SELECT MAX(t.year) AS yr
  FROM equity_gap eg
  JOIN dim_time t ON eg.time_id = t.id
  WHERE eg.indicator_id = ${safeIndicatorId}
`))[0]?.yr ?? 2024) : 2024;

// Summary: compute gap + propagated CI directly from source estimates
// gap_SE = sqrt(target_SE² + ref_SE²), where SE = (upper_ci - lower_ci) / 3.92
const summaryGaps = safeIndicatorId != null ? Array.from(await db.query(`
  WITH target AS (
    SELECT fhi.geography_id, fhi.ethnicity_id,
      AVG(fhi.value)          AS value,
      AVG(fhi.value_lower_ci) AS lower_ci,
      AVG(fhi.value_upper_ci) AS upper_ci
    FROM fact_health_indicator fhi
    JOIN dim_time t ON fhi.time_id = t.id
    WHERE fhi.indicator_id = ${safeIndicatorId}
      AND fhi.ethnicity_id IN (${safeEthnicities.length ? safeEthnicities.join(",") : "NULL"})
      AND t.year = ${latestYear}
    GROUP BY fhi.geography_id, fhi.ethnicity_id
  ),
  ref AS (
    SELECT fhi.geography_id,
      AVG(fhi.value)          AS value,
      AVG(fhi.value_lower_ci) AS lower_ci,
      AVG(fhi.value_upper_ci) AS upper_ci
    FROM fact_health_indicator fhi
    JOIN dim_time t ON fhi.time_id = t.id
    JOIN dim_ethnicity e ON fhi.ethnicity_id = e.id
    WHERE fhi.indicator_id = ${safeIndicatorId}
      AND e.name = 'European/Other' AND e.response_type = 'total_response'
      AND t.year = ${latestYear}
    GROUP BY fhi.geography_id
  )
  SELECT
    e.name  AS ethnicity,
    g.name  AS geography,
    g.level,
    i.unit,
    i.direction,
    ${latestYear} AS year,
    tgt.value                    AS target_value,
    tgt.lower_ci                 AS target_lower_ci,
    tgt.upper_ci                 AS target_upper_ci,
    r.value                      AS reference_value,
    tgt.value - r.value          AS absolute_gap,
    -- 95% CI for the gap (SE propagation for difference of two independent estimates)
    (tgt.value - r.value) - 1.96 * SQRT(
      POWER((tgt.upper_ci - tgt.lower_ci) / 3.92, 2) +
      POWER((r.upper_ci   - r.lower_ci  ) / 3.92, 2)
    ) AS gap_lower_ci,
    (tgt.value - r.value) + 1.96 * SQRT(
      POWER((tgt.upper_ci - tgt.lower_ci) / 3.92, 2) +
      POWER((r.upper_ci   - r.lower_ci  ) / 3.92, 2)
    ) AS gap_upper_ci,
    -- Significant = CI excludes zero
    CASE
      WHEN (tgt.value - r.value) - 1.96 * SQRT(
        POWER((tgt.upper_ci - tgt.lower_ci) / 3.92, 2) +
        POWER((r.upper_ci   - r.lower_ci  ) / 3.92, 2)
      ) > 0
      OR (tgt.value - r.value) + 1.96 * SQRT(
        POWER((tgt.upper_ci - tgt.lower_ci) / 3.92, 2) +
        POWER((r.upper_ci   - r.lower_ci  ) / 3.92, 2)
      ) < 0 THEN true ELSE false
    END AS significant,
    -- Gap direction
    CASE
      WHEN ABS(tgt.value - r.value) < 0.01 THEN 'neutral'
      WHEN i.direction = 'lower_better' AND tgt.value > r.value THEN 'adverse'
      WHEN i.direction = 'higher_better' AND tgt.value < r.value THEN 'adverse'
      ELSE 'favourable'
    END AS gap_direction
  FROM target tgt
  JOIN ref r ON tgt.geography_id = r.geography_id
  JOIN dim_ethnicity e ON tgt.ethnicity_id = e.id
  JOIN dim_geography g ON tgt.geography_id = g.id
  JOIN dim_indicator i ON i.id = ${safeIndicatorId}
  ORDER BY ABS(tgt.value - r.value) DESC
`)) : [];

// Trend: avg absolute gap by year × ethnicity, national only
const trendGaps = safeIndicatorId != null ? Array.from(await db.query(`
  SELECT
    t.year,
    e.name AS ethnicity,
    AVG(eg.absolute_gap) AS absolute_gap,
    FIRST(eg.gap_direction ORDER BY ABS(eg.absolute_gap) DESC) AS gap_direction
  FROM equity_gap eg
  JOIN dim_geography g ON eg.geography_id = g.id
  JOIN dim_ethnicity e ON eg.target_ethnicity_id = e.id
  JOIN dim_time t ON eg.time_id = t.id
  WHERE eg.indicator_id = ${safeIndicatorId}
    AND eg.target_ethnicity_id IN (${safeEthnicities.join(",") || "0"})
    AND g.level = 'national'
  GROUP BY t.year, e.name
  ORDER BY t.year, e.name
`)) : [];

const noEthnicitySelected = selectedEthnicities.length === 0;
const nationalGaps = summaryGaps.filter(d => d.level === "national");
const regionalGaps = summaryGaps.filter(d => d.level === "health_region");

// Policy events — turning points for chart annotation
const policyEvents = Array.from(await db.query(`
  SELECT
    YEAR(date::DATE) AS year,
    title,
    category,
    treaty_relevance
  FROM fact_policy_events
  WHERE tags LIKE '%turning_point%'
    AND YEAR(date::DATE) BETWEEN 2010 AND 2026
  ORDER BY date
`));
```

```js
// Gap direction colour scale (colour-blind safe, RdYlBu reversed)
const gapColor = (direction) => ({
  "adverse": "#d73027",
  "neutral": "#ffffbf",
  "favourable": "#4575b4",
})[direction] ?? "#636363";

const displayEthnicity = (name) => ({ "Maori": "Māori", "non-Maori": "non-Māori", "Pacific": "Pacific", "Asian": "Asian", "European/Other": "European/Other", "Total": "Total", "MELAA": "MELAA", "Other": "Other" })[name] ?? name;
```

```js
display(html`
  <div class="note">
    <strong style="display: block; margin-bottom: 0.4rem; color: #c0392b;">
      ⚠ Methodological note: all gaps shown here are most likely underestimates
    </strong>
    Every known bias in the underlying data runs in the same direction — toward understating disparity between Māori/Pacific and European/Other populations. Reasons include:
    <ul style="margin: 0.5rem 0 0; padding-left: 1.2rem;">
      <li><strong>Ethnic miscoding</strong>: ~20% of Māori are miscoded as European/Other in administrative records, contaminating the reference group upward and the target group downward.</li>
      <li><strong>Survey exclusions</strong>: NZHS excludes people in prisons, hospitals, and residential care — groups with disproportionately high Māori/Pacific representation and worse health outcomes.</li>
      <li><strong>Suppression of small cells</strong>: estimates with n &lt; 30 are hidden; these are concentrated in rural Māori/Pacific communities with the highest need.</li>
      <li><strong>No age standardisation</strong>: Māori/Pacific populations are younger on average, so crude rates understate age-adjusted disadvantage for conditions that worsen with age.</li>
      <li><strong>Total response vs prioritised ethnicity</strong>: total response inflates denominator counts for Māori/Pacific, suppressing apparent rates.</li>
    </ul>
    <span style="display: block; margin-top: 0.5rem; font-size: 0.9em;">
      Treat every gap on this page as a floor, not a ceiling.
    </span>
  </div>
`);
```

## Current Equity Gaps

## National Summary (${latestYear})

```js
if (noEthnicitySelected) {
  display(html`<p style="color: #636363; font-style: italic;">Select at least one ethnicity above to see gap data.</p>`);
} else if (nationalGaps.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">No equity gap data for this indicator yet.</p>`);
} else {
  const hasCI = nationalGaps.some(d => d.gap_lower_ci != null);

  // Narrative interpretation
  const worst = nationalGaps.reduce((a, b) => Math.abs(a.absolute_gap) > Math.abs(b.absolute_gap) ? a : b);
  const ind = indicators.find(d => d.id === indicatorId);
  const dirLabel = worst.direction === "lower_better" ? "higher" : "lower";
  const ratioText = worst.reference_value > 0
    ? `(${(worst.target_value / worst.reference_value).toFixed(1)}x the rate for European/Other)`
    : "";
  display(html`<p class="lead">
    <strong style="color: #c0392b;">${displayEthnicity(worst.ethnicity)}</strong> have a
    <strong>${Math.abs(worst.absolute_gap).toFixed(1)} percentage point</strong> ${dirLabel} rate
    for ${ind?.name?.toLowerCase() ?? "this indicator"} compared to European/Other
    ${ratioText}${worst.significant ? "" : " — though this difference is not statistically significant"}.
  </p>`);

  const nationalPlot = Plot.plot({
    title: `Gap vs. European/Other — national (${latestYear})`,
    subtitle: `${nationalGaps.filter(d => d.gap_direction === "adverse" && d.significant).length} of ${nationalGaps.length} gaps are statistically significant and adverse${hasCI ? " · Error bars show 95% CI · ~ = not significant" : ""}`,
    marginLeft: 100,
    marginRight: 20,
    width,
    x: { label: "Gap (percentage points)" },
    y: { label: null },
    color: { legend: true, domain: ["adverse", "neutral", "favourable"], range: ["#d73027", "#ffffbf", "#4575b4"] },
    marks: [
      Plot.ruleX([0]),
      // Bars — faded if not significant
      Plot.barX(nationalGaps, {
        x: "absolute_gap",
        y: "ethnicity",
        fill: "gap_direction",
        fillOpacity: d => d.significant ? 1.0 : 0.35,
        tip: true,
        title: d => [
          `${d.ethnicity}: ${d.absolute_gap?.toFixed(1)} pp (${d.gap_direction})`,
          `95% CI: [${d.gap_lower_ci?.toFixed(1)}, ${d.gap_upper_ci?.toFixed(1)}] pp`,
          d.significant ? "✓ Statistically significant" : "~ Not statistically significant",
          `Ref (European/Other): ${d.reference_value?.toFixed(1)}${d.unit}`,
          `This group: ${d.target_value?.toFixed(1)}${d.unit}`,
        ].join("\n"),
      }),
      // CI whisker line
      ...(hasCI ? [
        Plot.ruleX(nationalGaps.filter(d => d.gap_lower_ci != null), {
          x1: "gap_lower_ci",
          x2: "gap_upper_ci",
          y: "ethnicity",
          stroke: "#222",
          strokeWidth: 1.5,
          strokeOpacity: 0.7,
        }),
        // CI end caps
        Plot.tickX(nationalGaps.filter(d => d.gap_lower_ci != null), {
          x: "gap_lower_ci", y: "ethnicity", stroke: "#222", strokeWidth: 1.5,
        }),
        Plot.tickX(nationalGaps.filter(d => d.gap_upper_ci != null), {
          x: "gap_upper_ci", y: "ethnicity", stroke: "#222", strokeWidth: 1.5,
        }),
      ] : []),
      // Inline label: ~ prefix for non-significant
      Plot.text(nationalGaps, {
        x: d => d.absolute_gap / 2,
        y: "ethnicity",
        text: d => `${d.significant ? "" : "~ "}${d.absolute_gap >= 0 ? "+" : ""}${d.absolute_gap?.toFixed(1)} pp`,
        textAnchor: "middle",
        fontSize: 11,
        fontWeight: "600",
        fill: d => d.significant ? "white" : "#555",
      }),
    ],
  });
  display(nationalPlot);
  display(exportButtons(nationalPlot, nationalGaps, { filename: "equity-gap-national" }));

  // Non-significant gaps note
  const nonSig = nationalGaps.filter(d => !d.significant);
  if (nonSig.length > 0) {
    display(html`<p class="note">
      <strong>~</strong> ${nonSig.map(d => d.ethnicity).join(", ")}: gap CI crosses zero —
      difference from European/Other is not statistically significant at 95% confidence.
    </p>`);
  }

  display(html`<p class="methodology">
    <strong>CI note:</strong> Error bars assume the two survey estimates (target group vs. European/Other) are
    statistically independent. In a complex survey design they are correlated, so these CIs are
    <em>conservatively wide</em> — reported significance is a lower bound. Exact gap CIs require NZHS unit record
    microdata for covariance estimation. Treat "not significant" with caution, not as evidence of no gap.
  </p>`);
}
```

## Trend Over Time

```js
if (trendGaps.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">No trend data available.</p>`);
} else {
  // Wong colorblind-safe palette (Nat Methods 2011)
  const ethnicityColors = { "Māori": "#e69f00", "Pacific": "#56b4e9", "Asian": "#009e73" };
  // Map ethnicity display names for chart rendering
  const trendDisplay = trendGaps.map(d => ({ ...d, ethLabel: displayEthnicity(d.ethnicity) }));

  const trendPlot = Plot.plot({
    title: "Equity gap trend — national (vs. European/Other)",
    marginLeft: 60,
    marginRight: 80,
    width,
    y: { label: "Gap (pp)", zero: true },
    x: { label: "Year", tickFormat: d => String(d) },
    color: { legend: true },
    marks: [
      Plot.ruleY([0], { stroke: "#ccc" }),
      Plot.lineY(trendDisplay, {
        x: "year",
        y: "absolute_gap",
        stroke: "ethLabel",
        strokeWidth: 2,
        tip: true,
      }),
      Plot.dot(trendDisplay, {
        x: "year",
        y: "absolute_gap",
        fill: "ethLabel",
        r: 3,
        tip: true,
        title: d => `${d.ethLabel} (${d.year}): ${d.absolute_gap >= 0 ? "+" : ""}${d.absolute_gap?.toFixed(1)} pp (${d.gap_direction})`,
      }),
      Plot.text(trendDisplay.filter(d => d.year === latestYear), {
        x: "year",
        y: "absolute_gap",
        text: "ethLabel",
        dx: 6,
        textAnchor: "start",
        fontSize: 11,
      }),
      // COVID structural break
      Plot.ruleX([2020], { stroke: "#636363", strokeDasharray: "6,3", strokeWidth: 1.5 }),
      Plot.text([{ year: 2020, label: "COVID-19" }], {
        x: "year",
        y: () => Math.max(...trendGaps.map(d => d.absolute_gap ?? 0)),
        text: "label",
        dx: 4,
        textAnchor: "start",
        fontSize: 10,
        fill: "#636363",
        fontStyle: "italic",
      }),
      // Policy turning points
      Plot.ruleX(policyEvents, {
        x: "year",
        stroke: d => d.category === "repeal" ? "#e74c3c" : "#9b59b6",
        strokeWidth: 1,
        strokeDasharray: "2,4",
        title: d => d.title,
      }),
      // Policy event labels at top of chart
      Plot.text(policyEvents, {
        x: "year",
        frameAnchor: "top",
        dy: 6,
        text: d => d.title.length > 20 ? d.title.slice(0, 18) + "…" : d.title,
        fontSize: 8,
        fill: d => d.category === "repeal" ? "#e74c3c" : "#9b59b6",
        rotate: -45,
        textAnchor: "start",
      }),
    ],
  });
  display(trendPlot);
  display(exportButtons(trendPlot, trendGaps, { filename: "equity-gap-trend" }));

  display(html`<p class="note">
    <strong>Note</strong>: the dashed vertical line marks 2020. Data from 2020–2022 reflects pandemic
    disruption — reduced survey participation, deferred care, and changed service use patterns — and
    is <em>not directly comparable</em> to other years. Treat trend direction across this break with caution.
  </p>`);
}
```

## Regional Map (${latestYear})

```js
{
  if (regionalGaps.length === 0) {
    display(html`
      <div class="note" style="text-align: center;">
        <div style="font-size: 2.5rem; margin-bottom: 0.5rem; opacity: 0.4;">🗺</div>
        <p style="font-weight: 600; margin: 0 0 0.5rem;">No regional map for this selection</p>
        <p style="font-size: 0.85em; margin: 0;">
          The NZ Health Survey reports ethnicity breakdowns and regional breakdowns separately.
          Cross-tabulations (e.g. Māori in Northern region) are not published, so regional equity
          gaps cannot be computed from this source.
        </p>
      </div>
    `);
  } else {
    const ethnicityLabel = ethnicities.find(e => selectedEthnicities.includes(e.id))?.name ?? "selected groups";
    display(html`<div style="display:flex; gap: 2rem; align-items: flex-start; flex-wrap: wrap;">`);
    display(choropleth(nzTopo, regionalGaps, {
      width: 380,
      ethnicity: ethnicityLabel,
      title: `Equity gap by health region (${latestYear})`,
    }));
    display(html`
      <div style="flex:1; min-width:220px; font-size:0.85em; color: var(--theme-foreground-muted, #555); padding-top: 2rem;">
        <p><strong>How to read:</strong> Each DHB is coloured by its health region's equity gap for the selected indicator and ethnicity.</p>
        <div style="display:flex; flex-direction:column; gap:0.4rem; margin-top:0.75rem;">
          <span><span style="display:inline-block; width:14px; height:14px; background:#c0392b; border-radius:2px; vertical-align:middle; margin-right:4px;"></span> Adverse gap (Māori/Pacific worse)</span>
          <span><span style="display:inline-block; width:14px; height:14px; background:#4575b4; border-radius:2px; vertical-align:middle; margin-right:4px;"></span> Favourable gap</span>
          <span><span style="display:inline-block; width:14px; height:14px; background:#ffffbf; border:1px solid var(--theme-foreground-faintest, #ccc); border-radius:2px; vertical-align:middle; margin-right:4px;"></span> Neutral / no gap</span>
          <span><span style="display:inline-block; width:14px; height:14px; background:#e0e0e0; border-radius:2px; vertical-align:middle; margin-right:4px;"></span> No data</span>
        </div>
        <p style="margin-top:0.75rem;">Geography: 20 legacy DHBs coloured by their parent health region. Data is only available at the 4-region level from NZHS.</p>
      </div>
    `);
    display(html`</div>`);
  }
}
```

## Regional Breakdown (${latestYear})

```js
if (regionalGaps.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">No regional equity gap data for this indicator. The NZ Health Survey reports ethnicity breakdowns and regional breakdowns separately — cross-tabulations (Māori in Northern region) are not published, so regional equity gaps cannot be computed from this source.</p>`);
} else {
  const sorted = [...regionalGaps].sort((a, b) => a.absolute_gap - b.absolute_gap);
  display(Plot.plot({
    title: `Equity gap by region (${latestYear})`,
    subtitle: `${sorted.filter(d => d.gap_direction === "adverse").length} of ${sorted.length} region–ethnicity combinations show adverse gaps`,
    marginLeft: 200,
    marginRight: 60,
    width,
    height: Math.max(300, sorted.length * 22),
    x: { label: "Gap (percentage points)" },
    y: { domain: sorted.map(d => `${d.geography} — ${d.ethnicity}`) },
    color: { domain: ["adverse", "neutral", "favourable"], range: ["#d73027", "#ffffbf", "#4575b4"] },
    marks: [
      Plot.ruleX([0]),
      Plot.barX(sorted, {
        x: "absolute_gap",
        y: d => `${d.geography} — ${d.ethnicity}`,
        fill: "gap_direction",
        tip: true,
        title: d => `${d.geography} — ${d.ethnicity}: ${d.absolute_gap?.toFixed(1)} pp (${d.gap_direction})`,
      }),
    ],
  }));
}
```

## Data Table

```js
display(Inputs.table(summaryGaps, {
  columns: ["geography", "ethnicity", "reference_value", "target_value", "absolute_gap", "gap_lower_ci", "gap_upper_ci", "significant", "gap_direction"],
  header: {
    geography: "Region",
    ethnicity: "Ethnicity",
    reference_value: "Ref (Eur/Other)",
    target_value: "This group",
    absolute_gap: "Gap (pp)",
    gap_lower_ci: "CI lower",
    gap_upper_ci: "CI upper",
    significant: "Sig.",
    gap_direction: "Direction",
  },
  format: {
    reference_value: d => d?.toFixed(1) ?? "—",
    target_value: d => d?.toFixed(1) ?? "—",
    absolute_gap: d => (d >= 0 ? "+" : "") + (d?.toFixed(1) ?? "—"),
    gap_lower_ci: d => d != null ? (d >= 0 ? "+" : "") + d.toFixed(1) : "—",
    gap_upper_ci: d => d != null ? (d >= 0 ? "+" : "") + d.toFixed(1) : "—",
    significant: d => d ? "✓" : "~",
  },
}));
```

<details class="details-panel" style="margin-top: 2rem;">
<summary style="cursor: pointer; padding: 1rem; font-size: 1.1em; font-weight: 600; color: var(--theme-foreground, #1e293b);">
Why these gaps are underestimates — deprivation, life expectancy, and measurement bias
</summary>
<div style="padding: 0 1rem 1rem;">

## Deprivation Context (NZDep2018)

```js
const nzdep = Array.from(await db.query(`
  SELECT g.name AS geography, g.level,
    nd.nzdep_mean_score, nd.pct_q1, nd.pct_q2, nd.pct_q3, nd.pct_q4, nd.pct_q5,
    nd.sa1_count
  FROM fact_nzdep nd
  JOIN dim_geography g ON nd.geography_id = g.id
  ORDER BY nd.nzdep_mean_score DESC
`));

const regionalNzdep = nzdep.filter(d => d.level === "health_region");
```

```js
if (regionalNzdep.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">NZDep data not yet available.</p>`);
} else {
  display(Plot.plot({
    title: "Deprivation quintile distribution by health region (NZDep2018)",
    subtitle: "Q5 = most deprived 20% of areas. Regions with more Q5 areas have structurally worse social determinants.",
    marginLeft: 220,
    width,
    height: 200,
    x: { label: "Share of areas (%)", domain: [0, 100] },
    y: { domain: regionalNzdep.map(d => d.geography) },
    color: {
      domain: ["Q1 (least)", "Q2", "Q3", "Q4", "Q5 (most)"],
      range: ["#4575b4", "#91bfdb", "#ffffbf", "#fc8d59", "#d73027"],
      legend: true,
    },
    marks: [
      // Stacked bars: Q1 through Q5
      ...[
        ["pct_q1", "Q1 (least)", 0],
        ["pct_q2", "Q2", 1],
        ["pct_q3", "Q3", 2],
        ["pct_q4", "Q4", 3],
        ["pct_q5", "Q5 (most)", 4],
      ].map(([field, label, idx]) =>
        Plot.barX(regionalNzdep, {
          x: d => d[field],
          x1: d => [0, d.pct_q1, d.pct_q1+d.pct_q2, d.pct_q1+d.pct_q2+d.pct_q3, d.pct_q1+d.pct_q2+d.pct_q3+d.pct_q4][idx],
          x2: d => [d.pct_q1, d.pct_q1+d.pct_q2, d.pct_q1+d.pct_q2+d.pct_q3, d.pct_q1+d.pct_q2+d.pct_q3+d.pct_q4, 100][idx],
          y: "geography",
          fill: label,
          tip: true,
          title: d => `${d.geography} ${label}: ${d[field]?.toFixed(1)}%`,
        })
      ),
    ],
  }));
  display(html`<p class="methodology">
    Source: NZDep2018 — University of Otago Department of Public Health. Aggregated from SA1 level to health region via legacy DHB assignments.
    Higher Q5 share correlates with higher Māori/Pacific population proportion and worse health outcomes across most indicators.
  </p>`);
}
```

## Life Expectancy Gap

```js
const lifeTables = Array.from(await db.query(`
  SELECT ethnicity_group, sex, age_band, age_from, ex
  FROM fact_life_tables
  WHERE age_from = 0
  ORDER BY ethnicity_group, sex
`));
```

```js
if (lifeTables.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">Life tables not yet available.</p>`);
} else {
  const lifeAtBirth = lifeTables.filter(d => d.age_from === 0);
  display(Plot.plot({
    title: "Life expectancy at birth — Māori vs non-Māori (2017–19)",
    subtitle: "Source: Stats NZ National and Subnational Period Life Tables 2017–19",
    marginLeft: 120,
    width: Math.min(width, 500),
    height: 200,
    x: { label: "Life expectancy (years)", domain: [60, 90] },
    y: { label: null },
    color: {
      domain: ["Māori", "non-Māori", "total"],
      range: ["#e69f00", "#0072b2", "#636363"],
    },
    marks: [
      Plot.ruleX([0]),
      Plot.barX(lifeAtBirth.filter(d => d.sex !== "total"), {
        x1: 60,
        x2: "ex",
        y: d => `${displayEthnicity(d.ethnicity_group)} (${d.sex})`,
        fill: d => displayEthnicity(d.ethnicity_group),
        tip: true,
        title: d => `${displayEthnicity(d.ethnicity_group)} ${d.sex}: ${d.ex?.toFixed(1)} years`,
      }),
      Plot.text(lifeAtBirth.filter(d => d.sex !== "total"), {
        x: "ex",
        y: d => `${displayEthnicity(d.ethnicity_group)} (${d.sex})`,
        text: d => `${d.ex?.toFixed(1)} yrs`,
        dx: 4,
        textAnchor: "start",
        fontSize: 11,
      }),
    ],
  }));
  display(html`<p class="methodology">
    The life expectancy gap (~7–8 years for males, ~7 years for females) is one of the
    most robust measures of health disparity and is <em>not</em> subject to the same
    measurement biases as survey-based rates — it derives from death registrations,
    which have near-complete ethnicity capture.
  </p>`);
}
```

## Bias Estimates — Gap Understatement

```js
const biasEstimates = Array.from(await db.query(`
  SELECT bias_type, direction, magnitude_lower_pct, magnitude_upper_pct,
    applies_to, notes, method, source, year
  FROM fact_bias_estimates
  ORDER BY magnitude_upper_pct DESC
`));
```

```js
if (biasEstimates.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">Bias estimates not yet available.</p>`);
} else {
  const biasTypeLabel = {
    ethnic_miscoding: "Ethnic miscoding",
    survey_exclusion: "Survey exclusion",
    age_composition: "Age composition",
    total_response_dilution: "Total response dilution",
    small_cell_suppression: "Small cell suppression",
  };

  display(html`
    <div style="margin: 1rem 0;">
      <p class="note" style="font-size: 0.95em; margin-bottom: 0.75rem;">
        Each row below is a separate, <em>compounding</em> source of understatement.
        They are not additive in a simple sense, but they all run in the same direction.
        The true equity gap for most indicators is likely larger than shown by the amounts below.
      </p>
      ${biasEstimates.map(b => html`
        <details class="details-panel" style="margin-bottom: 0.5rem;">
          <summary style="cursor: pointer; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: 600;">${biasTypeLabel[b.bias_type] ?? b.bias_type}
              <span style="font-weight: 400; color: var(--theme-foreground-muted, #666); margin-left: 0.5rem;">→ ${b.applies_to}</span>
            </span>
            <span style="
              background: var(--theme-background-alt, #fdf2f2); color: #c0392b; border-radius: 4px;
              padding: 2px 8px; font-size: 0.85em; font-weight: 600; white-space: nowrap;
            ">
              gap understated by ${b.magnitude_lower_pct?.toFixed(0)}–${b.magnitude_upper_pct?.toFixed(0)}%
            </span>
          </summary>
          <p style="margin: 0.5rem 0 0.25rem; font-size: 0.9em;">${b.notes}</p>
          <p class="methodology">
            <strong>Method:</strong> ${b.method}<br>
            <strong>Source:</strong> ${b.source}
          </p>
        </details>
      `)}
    </div>
  `);

  // Combined floor estimate (non-additive — conservative)
  const maxUpper = Math.max(...biasEstimates.map(b => b.magnitude_upper_pct ?? 0));
  const sumLower = biasEstimates.reduce((s, b) => s + (b.magnitude_lower_pct ?? 0), 0) * 0.5;
  display(html`
    <div class="note">
      <strong>Combined floor estimate (conservative, non-additive):</strong>
      gaps on this page are likely understated by at least ${sumLower.toFixed(0)}% and
      plausibly by ${maxUpper.toFixed(0)}%+ for indicators with strong age gradients or
      high rural Māori/Pacific populations. All biases point the same direction.
    </div>
  `);
}
```

## Prison Population Context

```js
const correctionsData = Array.from(await db.query(`
  SELECT e.name AS ethnicity, fc.total_count, fc.pct_of_total, fc.year
  FROM fact_corrections fc
  LEFT JOIN dim_ethnicity e ON fc.ethnicity_id = e.id
  ORDER BY fc.pct_of_total DESC
`));
```

```js
if (correctionsData.length > 0) {
  const maoriRow = correctionsData.find(d => d.ethnicity === "Maori");
  const totalPrison = correctionsData.reduce((s, d) => s + (d.total_count ?? 0), 0);
  display(html`
    <p class="note">
      Corrections NZ (Dec ${correctionsData[0]?.year}): total prison population <strong>${totalPrison.toLocaleString()}</strong>,
      of whom <strong style="color: #c0392b;">${maoriRow?.pct_of_total?.toFixed(1)}% are Māori</strong>
      (${maoriRow?.total_count?.toLocaleString()} people).
      The NZHS does not survey prison populations. Prison mental illness prevalence is ~50%;
      chronic disease rates are substantially elevated. These individuals are excluded from
      every gap calculation on this page.
    </p>
  `);
}
```

</div>
</details>

<div class="note">
<strong>Related:</strong> Equity gaps interact with workforce shortages — regions with the highest vacancy rates often have the worst outcomes. See <a href="./workforce">Workforce</a>. For how demand will grow in these regions, see <a href="./forecast">Demand Forecast</a>. For what the data cannot tell us, see <a href="./blind-spots">Blind Spots</a>.
</div>

```js
const sourceFreshness = Array.from(await db.query(`SELECT slug, name, last_ingested_at FROM dim_data_source`));
display(dataFreshness(sourceFreshness));
```

---

*Source: NZ Health Survey (Ministry of Health) | NZDep2018 (University of Otago) | Stats NZ Life Tables 2017-19 | Corrections NZ Dec 2023 | Electoral Commission 2023 | License: CC BY 4.0*

*Suppressed values (n < 30) are excluded from gap calculations. Reference population: European/Other, national level. All gaps shown are likely underestimates — see Bias Estimates section above.*
