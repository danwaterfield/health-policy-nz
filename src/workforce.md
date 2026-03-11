---
title: Workforce
---

# Workforce Pressure

GP density, nursing vacancy rates, and workforce shortfalls by region.

```js
import {exportButtons} from "./components/chart-export.js";
import {dataFreshness} from "./components/data-freshness.js";
```

```js
const db = await DuckDBClient.of({
  fact_workforce: FileAttachment("data/fact_workforce.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
  dim_data_source: FileAttachment("data/dim_data_source.parquet"),
});
```

```js
const workforce = Array.from(await db.query(`
  SELECT
    fw.role_type,
    AVG(fw.fte_filled)       AS fte_filled,
    AVG(fw.fte_vacant)       AS fte_vacant,
    AVG(fw.vacancy_rate)     AS vacancy_rate,
    AVG(fw.international_pct) AS international_pct,
    g.name AS region,
    g.level,
    t.year
  FROM fact_workforce fw
  JOIN dim_geography g ON fw.geography_id = g.id
  JOIN dim_time t ON fw.time_id = t.id
  GROUP BY fw.role_type, g.name, g.level, t.year
  ORDER BY t.year DESC, g.name
`));

const gps = workforce.filter(d => d.role_type === "gp");
const nurses = workforce.filter(d => d.role_type === "nurse");
const latestYear = workforce.length ? Math.max(...workforce.map(d => d.year).filter(Boolean)) : null;
const latestGps = gps.filter(d => d.year === latestYear);
const latestNurses = nurses.filter(d => d.year === latestYear && d.level === "district");
```

## GP Vacancy Rate by Region (${latestYear})

```js
if (latestGps.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">No workforce data available yet.</p>`);
} else {
  const sorted = [...latestGps].sort((a, b) => b.vacancy_rate - a.vacancy_rate);
  display(Plot.plot({
    title: "GP vacancy rate by region",
    marginLeft: 200,
    width,
    height: Math.max(300, sorted.length * 22),
    x: { label: "Vacancy rate (%)", domain: [0, Math.max(...sorted.map(d => (d.vacancy_rate ?? 0) * 100)) * 1.1] },
    y: { domain: sorted.map(d => d.region) },
    color: { legend: false },
    marks: [
      Plot.ruleX([8], { stroke: "#2d8a4e", strokeDasharray: "4,4" }),
      Plot.barX(sorted, {
        x: d => (d.vacancy_rate ?? 0) * 100,
        y: "region",
        fill: d => d.vacancy_rate > 0.15 ? "#c0392b" : d.vacancy_rate > 0.08 ? "#e5850b" : "#2d8a4e",
        tip: true,
        title: d => `${d.region}: ${((d.vacancy_rate ?? 0) * 100).toFixed(1)}% vacancy rate\nFTE filled: ${d.fte_filled ?? "—"}`,
      }),
    ],
  }));
  display(html`<p style="font-size: 0.82em; color: #555; margin-top: 0.25rem;">
    <span style="color: #2d8a4e;">■</span> &lt;8% (meeting GPS target)
    <span style="color: #e5850b; margin-left: 1rem;">■</span> 8–15% (at risk)
    <span style="color: #c0392b; margin-left: 1rem;">■</span> &gt;15% (critical shortage)
    <span style="color: #2d8a4e; margin-left: 1rem;">- -</span> 8% GPS target threshold
  </p>`);
}
```

## International Recruitment Dependency

```js
if (latestGps.length > 0) {
  const withIntl = latestGps.filter(d => d.international_pct !== null);
  if (withIntl.length > 0) {
    display(Plot.plot({
      title: "GP workforce: international recruitment % by region",
      marginLeft: 200,
      width,
      height: Math.max(200, withIntl.length * 18),
      x: { label: "International GPs (%)" },
      marks: [
        Plot.barX(withIntl.sort((a, b) => b.international_pct - a.international_pct), {
          x: d => (d.international_pct ?? 0) * 100,
          y: "region",
          fill: "#7b6db8",
          tip: true,
          title: d => `${d.region}: ${((d.international_pct ?? 0) * 100).toFixed(1)}% internationally trained`,
        }),
      ],
    }));
  } else {
    display(html`<p style="color: #636363; font-style: italic;">No international recruitment data available.</p>`);
  }
} else {
  display(html`<p style="color: #636363; font-style: italic;">No GP workforce data available yet.</p>`);
}
```

## Nursing Vacancy by Region

```js
if (latestNurses.length > 0) {
  display(Plot.plot({
    title: "Nursing vacancy rate by district",
    marginLeft: 200,
    width,
    height: Math.max(200, latestNurses.length * 18),
    x: { label: "Vacancy rate (%)" },
    marks: [
      Plot.ruleX([12], { stroke: "#e5850b", strokeDasharray: "4,4" }),
      Plot.barX(latestNurses.sort((a, b) => b.vacancy_rate - a.vacancy_rate), {
        x: d => (d.vacancy_rate ?? 0) * 100,
        y: "region",
        fill: d => d.vacancy_rate > 0.20 ? "#c0392b" : "#e5850b",
        tip: true,
        title: d => `${d.region}: ${((d.vacancy_rate ?? 0) * 100).toFixed(1)}% vacancy`,
      }),
    ],
  }));
  display(html`<p style="font-size: 0.82em; color: #555; margin-top: 0.25rem;">
    <span style="color: #e5850b;">■</span> &lt;20% vacancy
    <span style="color: #c0392b; margin-left: 1rem;">■</span> &gt;20% vacancy (critical)
    <span style="color: #e5850b; margin-left: 1rem;">- -</span> 12% reference threshold
  </p>`);
} else {
  display(html`<p style="color: #636363; font-style: italic;">No nursing vacancy data available yet.</p>`);
}
```

## Workforce Data Summary

```js
display(Inputs.table(workforce.filter(d => d.year === latestYear), {
  columns: ["region", "role_type", "fte_filled", "fte_vacant", "vacancy_rate", "international_pct"],
  header: {
    region: "Region",
    role_type: "Role",
    fte_filled: "FTE (Filled)",
    fte_vacant: "FTE (Vacant)",
    vacancy_rate: "Vacancy %",
    international_pct: "Intl %",
  },
  format: {
    vacancy_rate: d => d ? `${(d * 100).toFixed(1)}%` : "—",
    international_pct: d => d ? `${(d * 100).toFixed(1)}%` : "—",
    fte_filled: d => d?.toFixed(0) ?? "—",
    fte_vacant: d => d?.toFixed(0) ?? "—",
  },
}));
display(exportButtons(null, workforce.filter(d => d.year === latestYear), { filename: "workforce-data" }));
```

```js
const sourceFreshness = Array.from(await db.query(`SELECT slug, name, last_ingested_at FROM dim_data_source`));
display(dataFreshness(sourceFreshness));
```

---

*Source: Health New Zealand / Medical Council NZ workforce reports (seed data, manually compiled) | Crown Copyright*

<div style="
  border-left: 4px solid #e5850b;
  background: #fef9ec;
  border-radius: 0 6px 6px 0;
  padding: 0.75rem 1rem;
  margin: 1rem 0;
  font-size: 0.85em;
  color: #222;
">
  <strong style="color: #b36000;">⚠ Data provenance note</strong><br>
  2023 district figures are sourced from Health NZ and Medical Council of NZ annual workforce reports (manually extracted — no machine-readable download is available). <strong>2024 district-level figures are modelled estimates</strong>, extrapolated from 2023 values using the observed national trend (vacancy rates +0.7–2 pp, FTE counts −1–2%). They should not be cited as official statistics. The national 2024 totals are from Health NZ published data and are authoritative. District-level 2024 data will be updated when Health NZ publishes the next workforce census.
</div>

*Note: Nursing vacancy data is less complete than GP data — see [Blind Spots](/blind-spots) for details.*
