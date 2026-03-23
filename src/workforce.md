---
title: Workforce

---

# Workforce Pressure

<p class="lead">GP density, nursing vacancy rates, and workforce shortfalls by region.</p>

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

```js
// Computed workforce narrative headline
{
  const gpRegional = latestGps.filter(d => d.level !== "national");
  if (gpRegional.length > 0) {
    const exceed = gpRegional.filter(d => (d.vacancy_rate ?? 0) > 0.08);
    const worst = [...gpRegional].sort((a, b) => (b.vacancy_rate ?? 0) - (a.vacancy_rate ?? 0))[0];
    const worstPct = ((worst.vacancy_rate ?? 0) * 100).toFixed(1);
    display(html`<p>
      <span class="fig fig-adverse">${exceed.length}</span> of ${gpRegional.length} regions exceed the 8% GP vacancy threshold. The most acute shortage is in <strong>${worst.region}</strong> at <span class="fig fig-adverse">${worstPct}%</span> vacancy.
    </p>`);
  } else if (latestGps.length === 0) {
    // No data — show nothing
  } else {
    display(html`<p>
      GP workforce data available for national level only.
    </p>`);
  }
}
```

## GP Vacancy Rate by Region (${latestYear})

```js
if (latestGps.length === 0) {
  display(html`<p style="color: #636363; font-style: italic;">No workforce data available yet.</p>`);
} else {
  const sorted = [...latestGps].sort((a, b) => b.vacancy_rate - a.vacancy_rate);
  display(Plot.plot({
    title: "GP vacancy rate by region",
    subtitle: `${sorted.filter(d => (d.vacancy_rate ?? 0) > 0.08).length} of ${sorted.length} regions exceed the 8% GPS target`,
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
  display(html`<p class="methodology">
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
    const sorted = [...withIntl].sort((a, b) => b.international_pct - a.international_pct);
    display(Plot.plot({
      title: "GP workforce: international recruitment % by region",
      subtitle: `Range: ${(Math.min(...sorted.map(d => (d.international_pct ?? 0) * 100))).toFixed(0)}%–${(Math.max(...sorted.map(d => (d.international_pct ?? 0) * 100))).toFixed(0)}% across regions`,
      marginLeft: 200,
      width,
      height: Math.max(200, withIntl.length * 18),
      x: { label: "International GPs (%)" },
      marks: [
        Plot.barX(sorted, {
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
  const sorted = [...latestNurses].sort((a, b) => b.vacancy_rate - a.vacancy_rate);
  display(Plot.plot({
    title: "Nursing vacancy rate by district",
    subtitle: `${sorted.filter(d => (d.vacancy_rate ?? 0) > 0.20).length} districts above 20% critical threshold`,
    marginLeft: 200,
    width,
    height: Math.max(200, sorted.length * 18),
    x: { label: "Vacancy rate (%)" },
    marks: [
      Plot.ruleX([12], { stroke: "#e5850b", strokeDasharray: "4,4" }),
      Plot.barX(sorted, {
        x: d => (d.vacancy_rate ?? 0) * 100,
        y: "region",
        fill: d => d.vacancy_rate > 0.20 ? "#c0392b" : "#e5850b",
        tip: true,
        title: d => `${d.region}: ${((d.vacancy_rate ?? 0) * 100).toFixed(1)}% vacancy`,
      }),
    ],
  }));
  display(html`<p class="methodology">
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

<div class="aside">
<strong>Related:</strong> These workforce gaps interact with projected demand growth. See <a href="./forecast">Demand Forecast</a> for how demographic change will compound pressure on understaffed regions. For the equity implications, see <a href="./equity">Equity Gap Explorer</a>.
</div>

```js
const sourceFreshness = Array.from(await db.query(`SELECT slug, name, last_ingested_at FROM dim_data_source`));
display(dataFreshness(sourceFreshness));
```

---

*Source: Health New Zealand / Medical Council NZ workforce reports (seed data, manually compiled) | Crown Copyright*

<div class="aside">
  <strong>⚠ Data provenance note</strong><br>
  2023 district figures are sourced from Health NZ and Medical Council of NZ annual workforce reports (manually extracted — no machine-readable download is available). <strong>2024 district-level figures are modelled estimates</strong>, extrapolated from 2023 values using the observed national trend (vacancy rates +0.7–2 pp, FTE counts −1–2%). They should not be cited as official statistics. The national 2024 totals are from Health NZ published data and are authoritative. District-level 2024 data will be updated when Health NZ publishes the next workforce census.
</div>

*Note: Nursing vacancy data is less complete than GP data — see [Blind Spots](/blind-spots) for details.*
