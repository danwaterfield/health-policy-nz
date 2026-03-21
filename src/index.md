---
title: NZ Health System Dashboard
---

# NZ Health System Dashboard

A synthesis of public New Zealand health data — equity gaps, service access, workforce, and demand projections.

```js
import {dataFreshness} from "./components/data-freshness.js";
```

```js
const db = await DuckDBClient.of({
  dim_indicator: FileAttachment("data/dim_indicator.parquet"),
  dim_data_source: FileAttachment("data/dim_data_source.parquet"),
  equity_gap: FileAttachment("data/equity_gap.parquet"),
  dim_ethnicity: FileAttachment("data/dim_ethnicity.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
});
```

```js
const indicatorCount = Number(Array.from(await db.query("SELECT COUNT(*) AS n FROM dim_indicator"))[0].n);
const adverseGapCount = Number(Array.from(await db.query(`
  SELECT COUNT(DISTINCT indicator_id || '-' || target_ethnicity_id) AS n
  FROM equity_gap WHERE gap_direction = 'adverse'
`))[0].n);
const sourceCount = Number(Array.from(await db.query("SELECT COUNT(*) AS n FROM dim_data_source"))[0].n);
```

<div class="grid grid-cols-3" style="margin: 2rem 0;">
  <div class="card">
    <h2>${indicatorCount}</h2>
    <p>Health indicators tracked</p>
  </div>
  <div class="card" style="--card-color: #c0392b;">
    <h2>${adverseGapCount}</h2>
    <p>Indicator–ethnicity combinations with adverse gaps</p>
  </div>
  <div class="card">
    <h2>${sourceCount}</h2>
    <p>Public data sources ingested</p>
  </div>
</div>

## Key Findings

```js
// Top adverse gaps: latest year per indicator, national, Māori/Pacific only
const topGaps = Array.from(await db.query(`
  WITH latest AS (
    SELECT eg.indicator_id, eg.target_ethnicity_id, MAX(t.year) AS max_year
    FROM equity_gap eg
    JOIN dim_time t ON eg.time_id = t.id
    JOIN dim_geography g ON eg.geography_id = g.id
    WHERE g.level = 'national'
    GROUP BY eg.indicator_id, eg.target_ethnicity_id
  )
  SELECT
    i.name AS indicator,
    e.name AS ethnicity,
    AVG(eg.absolute_gap) AS absolute_gap,
    AVG(eg.reference_value) AS reference_value,
    AVG(eg.target_value) AS target_value,
    FIRST(eg.gap_direction) AS gap_direction,
    FIRST(i.unit) AS unit,
    l.max_year AS year
  FROM equity_gap eg
  JOIN dim_time t ON eg.time_id = t.id
  JOIN dim_geography g ON eg.geography_id = g.id
  JOIN dim_indicator i ON eg.indicator_id = i.id
  JOIN dim_ethnicity e ON eg.target_ethnicity_id = e.id
  JOIN latest l ON eg.indicator_id = l.indicator_id AND eg.target_ethnicity_id = l.target_ethnicity_id
  WHERE g.level = 'national'
    AND e.name IN ('Maori', 'Pacific')
    AND e.response_type = 'total_response'
    AND t.year = l.max_year
    AND eg.gap_direction = 'adverse'
  GROUP BY i.name, e.name, l.max_year
  ORDER BY ABS(AVG(eg.absolute_gap)) DESC
  LIMIT 6
`));
```

```js
const severityColor = (gap) => Math.abs(gap) >= 20 ? "#c0392b" : Math.abs(gap) >= 10 ? "#e5850b" : "#2d7d46";
const displayEthnicity = (name) => ({ "Maori": "Māori", "Pacific": "Pacific", "Asian": "Asian", "European/Other": "European/Other", "Total": "Total", "MELAA": "MELAA", "Other": "Other" })[name] ?? name;

display(html`
  <div class="stat-grid">
    ${topGaps.map(d => {
      const gap = d.absolute_gap;
      const color = severityColor(gap);
      const abs = Math.abs(gap).toFixed(1);
      return html`
        <div class="stat-card" style="border-left: 4px solid ${color};">
          <div class="stat-label">${displayEthnicity(d.ethnicity)} · ${d.year}</div>
          <div class="stat-value" style="color: ${color};">
            ${gap >= 0 ? "+" : "−"}${abs} pp
          </div>
          <div style="font-size: 0.95em; font-weight: 600; margin: 0.25rem 0 0.5rem;">${d.indicator}</div>
          <div class="stat-sub">
            ${d.target_value?.toFixed(1)}${d.unit} vs ${d.reference_value?.toFixed(1)}${d.unit} for European/Other
          </div>
        </div>
      `;
    })}
  </div>
`);
```

```js
display(html`
  <p class="note">
    <strong style="color: #c0392b;">These figures are underestimates.</strong>
    Ethnic miscoding (~20% of Māori recorded as European/Other), NZHS exclusions (prisons, hospitals,
    residential care), suppression of small rural cells, and the absence of age standardisation all
    bias the measured gaps downward. Every number here is a floor, not a ceiling.
    See the <a href="/equity">Equity page</a> for full methodological detail.
  </p>
`);
```

## What This Dashboard Shows

This dashboard synthesises public NZ health data to surface:

- **Equity gaps** — where Māori, Pacific, and other communities experience worse health outcomes or access than European/Other New Zealanders
- **Service access** — wait times, volumes, and pressure on health services
- **Workforce** — GP density, nurse vacancy rates, and regional shortfalls
- **Demand projections** — forward estimates of health service need based on demographic change
- **Blind spots** — where the data simply does not exist to answer important questions

## Navigate

| Page | What you'll find |
|---|---|
| [Indicator Explorer](/explorer) | Multi-year trends by indicator and ethnicity |
| [Equity](/equity) | Equity gap explorer by indicator and ethnicity |
| [GPS Scorecard](/scorecard) | Government Policy Statement 2024–27 accountability |
| [Workforce](/workforce) | GP density and workforce pressure by region |
| [Demand Forecast](/forecast) | Projected demand under demographic scenarios |
| [COVID Impact](/trends) | Pre- vs post-COVID trajectory shift analysis |
| [Blind Spots](/blind-spots) | Known gaps in NZ health data |

```js
const sourceFreshness = Array.from(await db.query(`SELECT slug, name, last_ingested_at FROM dim_data_source`));
display(dataFreshness(sourceFreshness));
```

---

*Data: Ministry of Health NZ, Health New Zealand, Stats NZ. Updated weekly. [Source code on GitHub](https://github.com/danwaterfield/health-policy-nz).*
