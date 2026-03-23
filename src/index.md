---
title: NZ Health System Dashboard
toc: false
---

```js
import * as topojson from "npm:topojson-client";
import L from "npm:leaflet";
```

```js
const sa2Topo = await FileAttachment("data/nz-sa2.json").json();
```

```js
const db = await DuckDBClient.of({
  fact_access: FileAttachment("data/fact_access.parquet"),
  fact_sa2_nzdep: FileAttachment("data/fact_sa2_nzdep.parquet"),
  fact_facilities: FileAttachment("data/fact_facilities.parquet"),
  equity_gap: FileAttachment("data/equity_gap.parquet"),
  dim_indicator: FileAttachment("data/dim_indicator.parquet"),
  dim_ethnicity: FileAttachment("data/dim_ethnicity.parquet"),
  dim_time: FileAttachment("data/dim_time.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
});
```

```js
const accessData = Array.from(await db.query(`
  SELECT * FROM fact_access WHERE nearest_minutes IS NOT NULL AND facility_type = 'gp'
`));
const sa2Nzdep = Array.from(await db.query(`
  SELECT sa2_code, nzdep_quintile FROM fact_sa2_nzdep WHERE nzdep_quintile IS NOT NULL
`));
const facilities = Array.from(await db.query(`
  SELECT facility_type, latitude, longitude FROM fact_facilities
`));
const adverseGapCount = Number(Array.from(await db.query(`
  SELECT COUNT(DISTINCT indicator_id || '-' || target_ethnicity_id) AS n
  FROM equity_gap WHERE gap_direction = 'adverse'
`))[0].n);
```

```js
// Build lookups
const accessLookup = new Map();
for (const row of accessData) {
  const existing = accessLookup.get(row.sa2_code);
  if (!existing || row.nearest_minutes < existing.nearest_minutes) {
    accessLookup.set(row.sa2_code, row);
  }
}

// Quintile stats for the overlay
const q5Rows = accessData.filter(d => d.nzdep_quintile === 5 && d.nearest_minutes != null);
const q1Rows = accessData.filter(d => d.nzdep_quintile === 1 && d.nearest_minutes != null);
const q5Over30Pct = q5Rows.length > 0
  ? (q5Rows.filter(d => d.nearest_minutes > 30).length / q5Rows.length * 100).toFixed(0)
  : "—";
const q1Over30Pct = q1Rows.length > 0
  ? (q1Rows.filter(d => d.nearest_minutes > 30).length / q1Rows.length * 100).toFixed(0)
  : "—";
```

```js
{
  // Decode TopoJSON
  const objectKey = Object.keys(sa2Topo.objects)[0];
  const sa2All = topojson.feature(sa2Topo, sa2Topo.objects[objectKey]);
  const sa2Geojson = {
    type: "FeatureCollection",
    features: sa2All.features.filter(f => {
      const name = f.properties?.sa2_name || "";
      if (name.startsWith("Oceanic") || name.includes("Chatham")) return false;
      if (name.startsWith("Inlet") || name.startsWith("Inland water")) return false;
      return true;
    }),
  };

  function travelColor(mins) {
    if (mins == null) return "#f0f0f0";
    if (mins <= 2) return "#ffffcc";
    if (mins <= 5) return "#ffeda0";
    if (mins <= 10) return "#fed976";
    if (mins <= 15) return "#feb24c";
    if (mins <= 20) return "#fd8d3c";
    if (mins <= 30) return "#fc4e2a";
    if (mins <= 45) return "#e31a1c";
    if (mins <= 60) return "#bd0026";
    return "#800026";
  }

  // Wrapper: map + overlay
  const wrapper = document.createElement("div");
  wrapper.style.cssText = "position:relative; width:100%; margin: 0 -1rem; padding: 0;";

  const container = document.createElement("div");
  container.style.cssText = "width:100%; height:85vh; min-height:500px;";
  wrapper.appendChild(container);

  // Overlay with key finding — built with safe DOM methods
  const overlay = document.createElement("div");
  overlay.style.cssText = `
    position:absolute; top:2rem; left:2rem; z-index:1000;
    background:rgba(255,255,255,0.92); backdrop-filter:blur(8px);
    padding:1.5rem 2rem; max-width:380px; border-radius:4px;
    box-shadow:0 2px 12px rgba(0,0,0,0.12);
    font-family:-apple-system,system-ui,sans-serif;
  `;

  const label = document.createElement("div");
  label.style.cssText = "font-size:0.7rem;text-transform:uppercase;letter-spacing:0.1em;color:#888;margin-bottom:0.5rem;";
  label.textContent = "NZ Health System Dashboard";
  overlay.appendChild(label);

  const headline = document.createElement("div");
  headline.style.cssText = "font-size:1.6rem;font-weight:800;line-height:1.2;color:#1a1a1a;margin-bottom:0.75rem;";
  headline.textContent = `${q5Over30Pct}% of the most deprived communities are 30+ min from a GP`;
  overlay.appendChild(headline);

  const subtext = document.createElement("div");
  subtext.style.cssText = "font-size:0.85rem;color:#555;line-height:1.5;margin-bottom:1rem;";
  subtext.textContent = `vs ${q1Over30Pct}% in the least deprived. ${adverseGapCount} indicator\u2013ethnicity combinations show adverse health gaps.`;
  overlay.appendChild(subtext);

  const cta = document.createElement("a");
  cta.href = "./access";
  cta.style.cssText = "font-size:0.8rem;font-weight:600;color:#2166ac;text-decoration:none;";
  cta.textContent = "Explore spatial access \u2192";
  overlay.appendChild(cta);

  wrapper.appendChild(overlay);

  display(wrapper);

  await new Promise(r => setTimeout(r, 200));

  const map = L.map(container, { zoomSnap: 0.25, zoomControl: false }).setView([-41.3, 173.0], 5.5);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  setTimeout(() => map.invalidateSize(), 300);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '\u00a9 OSM \u00a9 CARTO',
    subdomains: "abcd",
    maxZoom: 15,
  }).addTo(map);

  L.geoJSON(sa2Geojson, {
    style: (feature) => {
      const code = feature.properties?.sa2_code;
      const access = accessLookup.get(code);
      return {
        fillColor: access ? travelColor(access.nearest_minutes) : "#f0f0f0",
        fillOpacity: 0.7,
        weight: 0.3,
        color: "#999",
        opacity: 0.3,
      };
    },
  }).addTo(map);

  // Facility dots
  for (const f of facilities) {
    if (f.latitude == null || f.longitude == null) continue;
    L.circleMarker([f.latitude, f.longitude], {
      radius: f.facility_type === "hospital" ? 3 : 1.5,
      fillColor: f.facility_type === "hospital" ? "#7b3294" : "#008837",
      color: "#fff",
      weight: 0.3,
      fillOpacity: 0.7,
    }).addTo(map);
  }
}
```

<div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:1rem; margin:2rem 0;">
<a href="./access" style="padding:1rem; border:1px solid #e0ddd8; border-radius:3px; text-decoration:none; color:inherit;">
<strong>Spatial Access</strong><br><span style="font-size:0.85rem;color:#888;">Drive times, deprivation, what-if scenarios</span>
</a>
<a href="./equity" style="padding:1rem; border:1px solid #e0ddd8; border-radius:3px; text-decoration:none; color:inherit;">
<strong>Equity Gaps</strong><br><span style="font-size:0.85rem;color:#888;">Ethnicity disparities across indicators</span>
</a>
<a href="./scorecard" style="padding:1rem; border:1px solid #e0ddd8; border-radius:3px; text-decoration:none; color:inherit;">
<strong>GPS Scorecard</strong><br><span style="font-size:0.85rem;color:#888;">2024-27 targets vs reality</span>
</a>
<a href="./workforce" style="padding:1rem; border:1px solid #e0ddd8; border-radius:3px; text-decoration:none; color:inherit;">
<strong>Workforce</strong><br><span style="font-size:0.85rem;color:#888;">GP vacancy, regional shortfalls</span>
</a>
<a href="./forecast" style="padding:1rem; border:1px solid #e0ddd8; border-radius:3px; text-decoration:none; color:inherit;">
<strong>Demand Forecast</strong><br><span style="font-size:0.85rem;color:#888;">Demographic projection scenarios</span>
</a>
<a href="./trends" style="padding:1rem; border:1px solid #e0ddd8; border-radius:3px; text-decoration:none; color:inherit;">
<strong>COVID Impact</strong><br><span style="font-size:0.85rem;color:#888;">Pre- vs post-pandemic trajectories</span>
</a>
</div>

<p style="font-size:0.75rem;color:#aaa;margin-top:1rem;">Data: Ministry of Health NZ, Health New Zealand, Stats NZ. <a href="https://github.com/danwaterfield/health-policy-nz" style="color:#aaa;">Source</a>.</p>
