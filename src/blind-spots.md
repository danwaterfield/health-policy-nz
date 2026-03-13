---
title: Blind Spots
---

# Data Blind Spots

Known gaps in NZ public health data that limit what this dashboard can show.

These are not analytical limitations — they are structural absences in the data itself.

```js
import {dataFreshness} from "./components/data-freshness.js";
```

```js
const db = await DuckDBClient.of({
  blind_spots: FileAttachment("data/blind_spots.parquet"),
  dim_data_source: FileAttachment("data/dim_data_source.parquet"),
});
```

```js
const spots = Array.from(await db.query(`
  SELECT domain, title, description, why_missing, proxy_limitation, severity, further_reading_url
  FROM blind_spots
  ORDER BY
    CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
    title
`));
```

```js
const severityConfig = {
  high: { color: "#c0392b", bg: "#fdf2f2", border: "#e8a8a8", label: "High severity", symbol: "▲" },
  medium: { color: "#e5850b", bg: "#fef9ec", border: "#f0d090", label: "Medium severity", symbol: "◆" },
  low: { color: "#2d8a4e", bg: "#f0f9f4", border: "#90d0aa", label: "Low severity", symbol: "●" },
};
```

```js
if (spots.length === 0) {
  display(html`
    <div style="padding: 2rem; background: #f5f5f5; border-radius: 8px; color: #555;">
      <p>Blind spots not yet populated.</p>
    </div>
  `);
} else {
  // Summary at top — gives context before reading individual cards
  const highCount = spots.filter(d => d.severity === "high").length;
  const medCount = spots.filter(d => d.severity === "medium").length;
  const lowCount = spots.filter(d => d.severity === "low").length;
  display(html`
    <div style="display: flex; gap: 1rem; flex-wrap: wrap; margin: 0.5rem 0 1.5rem;">
      <div style="padding: 0.5rem 1rem; background: #fdf2f2; border: 1px solid #e8a8a8; border-radius: 6px; color: #222; font-size: 0.9em;">
        <strong style="color: #c0392b;">▲ ${highCount}</strong> high severity
      </div>
      <div style="padding: 0.5rem 1rem; background: #fef9ec; border: 1px solid #f0d090; border-radius: 6px; color: #222; font-size: 0.9em;">
        <strong style="color: #e5850b;">◆ ${medCount}</strong> medium severity
      </div>
      ${lowCount > 0 ? html`
      <div style="padding: 0.5rem 1rem; background: #f0f9f4; border: 1px solid #90d0aa; border-radius: 6px; color: #222; font-size: 0.9em;">
        <strong style="color: #2d8a4e;">● ${lowCount}</strong> low severity
      </div>` : ""}
    </div>
  `);
  const cards = spots.map(spot => {
    const s = severityConfig[spot.severity] ?? severityConfig.medium;
    return html`
      <div style="
        border: 1px solid ${s.border};
        background: ${s.bg};
        border-radius: 8px;
        padding: 1.25rem 1.5rem;
        margin-bottom: 1rem;
      ">
        <div style="display: flex; align-items: flex-start; gap: 0.75rem; margin-bottom: 0.5rem;">
          <span style="
            color: ${s.color};
            font-size: 1.1em;
            font-weight: bold;
            flex-shrink: 0;
            padding-top: 2px;
          " aria-label="${s.label}">${s.symbol}</span>
          <div style="flex: 1;">
            <h3 style="margin: 0 0 0.25rem; font-size: 1.05em;">${spot.title}</h3>
            <span style="
              font-size: 0.75em;
              text-transform: uppercase;
              letter-spacing: 0.05em;
              color: ${s.color};
              font-weight: 600;
            ">${s.label}</span>
            ${spot.domain ? html`<span style="
              font-size: 0.72em;
              text-transform: uppercase;
              letter-spacing: 0.05em;
              color: #555;
              margin-left: 0.75rem;
              padding: 1px 6px;
              border: 1px solid #ccc;
              border-radius: 3px;
            ">${spot.domain}</span>` : ""}
          </div>
        </div>

        <p style="margin: 0.75rem 0 0.5rem; font-size: 0.95em; color: #222;">${spot.description}</p>

        <details style="margin-top: 0.75rem;">
          <summary style="cursor: pointer; color: #444; font-size: 0.9em; font-weight: 500;">
            Why is this missing?
          </summary>
          <p style="margin: 0.5rem 0 0; font-size: 0.9em; color: #333;">${spot.why_missing}</p>
        </details>

        <details style="margin-top: 0.5rem;">
          <summary style="cursor: pointer; color: #444; font-size: 0.9em; font-weight: 500;">
            Best available proxy &amp; limitations
          </summary>
          <p style="margin: 0.5rem 0 0; font-size: 0.9em; color: #333;">${spot.proxy_limitation}</p>
        </details>

        ${(() => {
          try {
            const u = spot.further_reading_url ? new URL(spot.further_reading_url) : null;
            return u && (u.protocol === "https:" || u.protocol === "http:") ? html`
              <div style="margin-top: 0.75rem;">
                <a href="${spot.further_reading_url}" target="_blank" rel="noopener noreferrer"
                   style="font-size: 0.85em; color: #2563eb; text-decoration: underline;">
                  Further reading →
                </a>
              </div>` : "";
          } catch { return ""; }
        })()}
      </div>
    `;
  });

  display(html`<div>${cards}</div>`);
}
```

## Summary

```js
if (spots.length > 0) {
  const highCount = spots.filter(d => d.severity === "high").length;
  const medCount = spots.filter(d => d.severity === "medium").length;

  display(html`
    <div style="display: flex; gap: 1.5rem; flex-wrap: wrap; margin: 1rem 0;">
      <div style="padding: 0.75rem 1.25rem; background: #fdf2f2; border: 1px solid #e8a8a8; border-radius: 6px; color: #222;">
        <strong style="color: #c0392b;">${highCount}</strong> high-severity gaps
      </div>
      <div style="padding: 0.75rem 1.25rem; background: #fef9ec; border: 1px solid #f0d090; border-radius: 6px; color: #222;">
        <strong style="color: #e5850b;">${medCount}</strong> medium-severity gaps
      </div>
    </div>
  `);
}
```

## What This Means for Interpretation

Every metric on this dashboard has a denominator — a population that was measured. The people not measured are often those with the highest need. Before citing figures from this dashboard:

1. Check whether the indicator covers the population you care about
2. Note sample suppression — small-n cells are hidden, often in rural and minority communities
3. Treat Māori/Pacific subgroup analyses as underestimates of true disparity
4. Do not use projections to justify reducing services in areas that appear to have low demand — low measured demand in deprived areas frequently reflects access barriers, not low need

```js
const sourceFreshness = Array.from(await db.query(`SELECT slug, name, last_ingested_at FROM dim_data_source`));
display(dataFreshness(sourceFreshness));
```

---

*Blind spots are identified by reviewing each data source's methodology notes and known limitations. This list is not exhaustive.*
