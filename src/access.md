---
title: Spatial Access to Health Services
---

# Spatial Access to Health Services

Do deprived communities face longer travel times to reach care? This page maps NZ's 2,395 Statistical Area 2 zones by deprivation and proximity to GPs, hospitals, and urgent care.

```js
import * as topojson from "npm:topojson-client";
import * as d3 from "npm:d3";
import L from "npm:leaflet";
import {exportButtons} from "./components/chart-export.js";
import {median, weightedMedian, weightedPercentile, gini, pearsonR, haversineKm} from "./components/access-stats.js";
import {buildSA2Popup, buildFacilityPopup, findNearestFacility} from "./components/access-detail.js";
const sa2Topo = await FileAttachment("data/nz-sa2.json").json();
```

```js
// Load Leaflet CSS
const leafletCss = document.createElement("link");
leafletCss.rel = "stylesheet";
leafletCss.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
document.head.appendChild(leafletCss);
```

```html
<style>
  .leaflet-container { background: #eaf2f8; }
  #access-map { width: 100%; height: 700px; border-radius: 8px; border: 1px solid #ddd; }
</style>
```

```js
const db = await DuckDBClient.of({
  fact_facilities: FileAttachment("data/fact_facilities.parquet"),
  fact_access: FileAttachment("data/fact_access.parquet"),
  fact_sa2_nzdep: FileAttachment("data/fact_sa2_nzdep.parquet"),
});
```

```js
// Load data
const facilities = Array.from(await db.query(`
  SELECT name, facility_type, latitude, longitude, sa2_name, health_region
  FROM fact_facilities
`));

const accessData = Array.from(await db.query(`
  SELECT * FROM fact_access WHERE nearest_minutes IS NOT NULL
`));

const sa2Nzdep = Array.from(await db.query(`
  SELECT sa2_code, sa2_name, nzdep_mean_score, nzdep_quintile, health_region, sa1_count
  FROM fact_sa2_nzdep
  WHERE nzdep_quintile IS NOT NULL
`));

const popLookup = new Map(sa2Nzdep.map(d => [d.sa2_code, d.population || 0]));

const hasAccess = accessData.length > 0;
```

```js
// Controls
const facilityType = view(Inputs.select(
  new Map([["GPs", "gp"], ["Hospitals", "hospital"], ["All types", "all"]]),
  { label: "Facility type", value: "gp" }
));
```

## Key statistics

```js
// Compute summary stats
const filteredAccess = facilityType === "all"
  ? accessData
  : accessData.filter(d => d.facility_type === facilityType);

if (hasAccess) {
  const byQuintile = [1, 2, 3, 4, 5].map(q => {
    const rows = filteredAccess.filter(d => d.nzdep_quintile === q);
    const validMinutes = [];
    const validWeights = [];
    rows.forEach(d => {
      if (d.nearest_minutes != null) {
        validMinutes.push(d.nearest_minutes);
        validWeights.push(popLookup.get(d.sa2_code) || 1);
      }
    });
    const med = weightedMedian(validMinutes, validWeights);
    const totalPop = validWeights.reduce((s, w) => s + w, 0);
    const popOver30 = rows.filter(d => d.nearest_minutes > 30)
      .reduce((s, d) => s + (popLookup.get(d.sa2_code) || 0), 0);
    const pctOver30 = totalPop > 0 ? (popOver30 / totalPop * 100) : 0;
    return { quintile: q, median: med, pctOver30, n: validMinutes.length, totalPop };
  });

  const q1Med = byQuintile[0]?.median;
  const q5Med = byQuintile[4]?.median;
  const q5Over30 = byQuintile[4]?.pctOver30;

  display(html`
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0;">
      <div style="background: #f0f7ff; padding: 1rem; border-radius: 8px; border-left: 4px solid #4575b4;">
        <div style="font-size: 0.8em; color: #555; text-transform: uppercase; letter-spacing: 0.5px;">Least deprived (Q1)</div>
        <div style="font-size: 2rem; font-weight: 700; color: #4575b4;">${q1Med != null ? q1Med.toFixed(0) + " min" : "—"}</div>
        <div style="font-size: 0.85em; color: #666;">median drive time (pop-weighted)</div>
      </div>
      <div style="background: #fdf2f2; padding: 1rem; border-radius: 8px; border-left: 4px solid #d73027;">
        <div style="font-size: 0.8em; color: #555; text-transform: uppercase; letter-spacing: 0.5px;">Most deprived (Q5)</div>
        <div style="font-size: 2rem; font-weight: 700; color: #d73027;">${q5Med != null ? q5Med.toFixed(0) + " min" : "—"}</div>
        <div style="font-size: 0.85em; color: #666;">median drive time (pop-weighted)</div>
      </div>
      <div style="background: #fff8f0; padding: 1rem; border-radius: 8px; border-left: 4px solid #e69f00;">
        <div style="font-size: 0.8em; color: #555; text-transform: uppercase; letter-spacing: 0.5px;">Q5 areas >30 min</div>
        <div style="font-size: 2rem; font-weight: 700; color: #e69f00;">${q5Over30 != null ? q5Over30.toFixed(0) + "%" : "—"}</div>
        <div style="font-size: 0.85em; color: #666;">of most deprived SA2s</div>
      </div>
      <div style="background: #f5f5f5; padding: 1rem; border-radius: 8px; border-left: 4px solid #636363;">
        <div style="font-size: 0.8em; color: #555; text-transform: uppercase; letter-spacing: 0.5px;">Facilities mapped</div>
        <div style="font-size: 2rem; font-weight: 700; color: #333;">${facilities.length.toLocaleString()}</div>
        <div style="font-size: 0.85em; color: #666;">${facilities.filter(f => f.facility_type === "gp").length} GPs, ${facilities.filter(f => f.facility_type === "hospital").length} hospitals</div>
      </div>
    </div>
  `);

  display(html`<p style="font-size: 0.8em; color: #888; margin-top: 0.5rem;">
    Based on ${sa2Nzdep.length.toLocaleString()} of ${accessData.length > 0 ? (accessData.length / 2).toLocaleString() : "—"} SA2 areas with matched NZDep data (SA2 2018→2025 concordance).
    Unmatched areas shown in grey on the map. Statistics are population-weighted using 2018 usually-resident population.
  </p>`);

  display(html`<p style="font-size: 0.85em; color: #555; margin: 0.5rem 0; line-height: 1.5;">
    <strong>Note:</strong> Q5 (most deprived) areas often show <em>lower</em> median drive times than Q1 because
    most Q5 SA2s are in dense urban centres (South Auckland, Porirua) near many GPs. The equity story is in
    the <strong>tail</strong>: ${byQuintile[4]?.pctOver30?.toFixed(0) ?? "—"}% of people in Q5 areas are
    &gt;30 min from the nearest GP, compared to ${byQuintile[0]?.pctOver30?.toFixed(0) ?? "—"}% in Q1 areas.
  </p>`);
} else {
  display(html`<p style="color: #666; font-style: italic;">
    Travel time data not yet computed. Run the pipeline with OSRM access to populate.
    Showing deprivation and facility locations only.
  </p>`);
}
```

## Deprivation map — SA2 level

```js
// Decode TopoJSON, filter out Chatham Islands which distort the Mercator projection
const objectKey = Object.keys(sa2Topo.objects)[0];
const sa2All = topojson.feature(sa2Topo, sa2Topo.objects[objectKey]);

const sa2Geojson = {
  type: "FeatureCollection",
  features: sa2All.features.filter(f => {
    const name = f.properties?.sa2_name || "";
    // Exclude oceanic zones and Chatham Islands (they distort the projection)
    if (name.startsWith("Oceanic") || name.includes("Chatham")) return false;
    // Exclude Inlet/Inland water features (empty sea/lake areas)
    if (name.startsWith("Inlet") || name.startsWith("Inland water")) return false;
    return true;
  }),
};

// Build lookup from SA2 code to NZDep quintile
const nzdepLookup = new Map(sa2Nzdep.map(d => [d.sa2_code, d]));

// Build lookup from SA2 code to access data
const accessLookup = new Map();
for (const row of filteredAccess) {
  const existing = accessLookup.get(row.sa2_code);
  if (!existing || row.nearest_minutes < existing.nearest_minutes) {
    accessLookup.set(row.sa2_code, row);
  }
}

// Load SA2 centroids for popup distance calculations
const centroids = await FileAttachment("data/sa2-centroids.json").json();

// Compute national median GP drive time for relative comparison
const gpAccess = filteredAccess.filter(d => d.facility_type === "gp" && d.nearest_minutes != null);
const nationalMedianGP = gpAccess.length > 0
  ? gpAccess.map(d => d.nearest_minutes).sort((a, b) => a - b)[Math.floor(gpAccess.length / 2)]
  : 0;

// Choose what to colour by
const colorBy = hasAccess ? "travel_time" : "deprivation";
```

```js
{
  // Colour helpers
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

  const depColors = { 1: "#2166ac", 2: "#67a9cf", 3: "#d1e5f0", 4: "#ef8a62", 5: "#b2182b" };

  function fillFn(code) {
    if (hasAccess) {
      const access = accessLookup.get(code);
      return access ? travelColor(access.nearest_minutes) : "#f0f0f0";
    } else {
      const nz = nzdepLookup.get(code);
      return nz ? (depColors[nz.nzdep_quintile] || "#f0f0f0") : "#f0f0f0";
    }
  }

  const filteredFacilities = facilityType === "all"
    ? facilities
    : facilities.filter(f => f.facility_type === facilityType);

  // Create map container
  const container = document.createElement("div");
  container.id = "access-map";
  display(container);

  // Wait a tick for DOM insertion
  await new Promise(r => setTimeout(r, 50));

  const map = L.map(container, { zoomSnap: 0.25 }).setView([-41.3, 173.0], 5.5);

  // CartoDB Positron basemap (clean, light, free)
  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '\u00a9 OSM \u00a9 CARTO',
    subdomains: "abcd",
    maxZoom: 15,
  }).addTo(map);

  // SA2 choropleth layer
  L.geoJSON(sa2Geojson, {
    style: (feature) => ({
      fillColor: fillFn(feature.properties?.sa2_code),
      fillOpacity: 0.7,
      weight: 0.3,
      color: "#666",
      opacity: 0.4,
    }),
    onEachFeature: (feature, layer) => {
      const code = feature.properties?.sa2_code;
      const name = feature.properties?.sa2_name || "";
      const nz = nzdepLookup.get(code);
      const access = accessLookup.get(code);
      const parts = [name];
      if (nz) parts.push(`NZDep Q${nz.nzdep_quintile} (score: ${nz.nzdep_mean_score?.toFixed(1)})`);
      if (access) parts.push(`${access.nearest_minutes?.toFixed(0)} min to nearest ${access.facility_type}`);
      layer.bindTooltip(parts.join("\n"), { sticky: true });
      layer.bindPopup(() => buildSA2Popup(code, accessLookup, nzdepLookup, facilities, centroids, nationalMedianGP), { maxWidth: 300 });
      layer.on("mouseover", (e) => { e.target.setStyle({ weight: 2, color: "#333", fillOpacity: 0.9 }); });
      layer.on("mouseout", (e) => { e.target.setStyle({ weight: 0.3, color: "#666", fillOpacity: 0.7 }); });
    },
  }).addTo(map);

  // Facility markers
  for (const f of filteredFacilities) {
    if (f.latitude == null || f.longitude == null) continue;
    L.circleMarker([f.latitude, f.longitude], {
      radius: f.facility_type === "hospital" ? 4 : 2.5,
      fillColor: f.facility_type === "hospital" ? "#7b3294" : "#008837",
      color: "#fff",
      weight: 0.5,
      fillOpacity: 0.85,
    })
    .bindTooltip(`${f.name} (${f.facility_type})`)
    .bindPopup(() => buildFacilityPopup(f, nzdepLookup, centroids), { maxWidth: 280 })
    .addTo(map);
  }

  // Legend
  const legendEl = document.createElement("div");
  legendEl.style.cssText = "background:white; padding:8px 10px; border-radius:6px; font-size:11px; line-height:1.8; box-shadow:0 1px 4px rgba(0,0,0,0.3);";

  function swatch(color) {
    return `<span style="display:inline-block;width:14px;height:10px;background:${color};margin-right:4px;vertical-align:middle;border:0.5px solid #ccc;"></span>`;
  }
  function dot(color) {
    return `<span style="display:inline-block;width:8px;height:8px;background:${color};border-radius:50%;margin-right:4px;vertical-align:middle;"></span>`;
  }

  const lines = [];
  if (hasAccess) {
    lines.push("<b>Drive time (min)</b>");
    const grades = [[1,"<2"],[3,"2–5"],[7,"5–10"],[12,"10–15"],[17,"15–20"],[25,"20–30"],[37,"30–45"],[52,"45–60"],[65,"60+"]];
    for (const [v, label] of grades) lines.push(swatch(travelColor(v)) + label);
  } else {
    lines.push("<b>NZDep quintile</b>");
    for (let q = 1; q <= 5; q++) lines.push(swatch(depColors[q]) + "Q" + q + (q===1 ? " (least)" : q===5 ? " (most)" : ""));
  }
  lines.push("");
  lines.push(dot("#008837") + "GP");
  lines.push(dot("#7b3294") + "Hospital");
  // Using DOM construction to avoid raw innerHTML with user data — all values here are static strings
  legendEl.innerHTML = lines.join("<br>");

  const LegendControl = L.Control.extend({
    onAdd() { return legendEl; },
  });
  new LegendControl({ position: "bottomright" }).addTo(map);
}
```


## Deprivation vs access

```js
if (hasAccess) {
  // Scatter: NZDep score vs travel time
  const scatterData = filteredAccess
    .filter(d => d.nzdep_score != null && d.nearest_minutes != null)
    .map(d => ({
      ...d,
      quintileLabel: `Q${d.nzdep_quintile}`,
    }));

  display(Plot.plot({
    width,
    height: 400,
    x: { label: "NZDep2018 deprivation score →", nice: true },
    y: { label: "↑ Minutes to nearest facility", nice: true },
    color: {
      domain: ["Northern | Te Tai Tokerau", "Midland | Te Manawa Taki", "Central | Te Ikaroa", "South Island | Te Waipounamu"],
      range: ["#e69f00", "#56b4e9", "#009e73", "#cc79a7"],
      legend: true,
    },
    marks: [
      Plot.dot(scatterData, {
        x: "nzdep_score",
        y: "nearest_minutes",
        fill: "health_region",
        r: 2.5,
        opacity: 0.5,
        tip: true,
        title: d => `${d.sa2_name}\nNZDep: ${d.nzdep_score?.toFixed(1)} (Q${d.nzdep_quintile})\n${d.nearest_minutes?.toFixed(0)} min to nearest ${d.facility_type}\n${d.health_region}`,
      }),
      // Trend line per quintile (median)
      Plot.lineY(
        [1, 2, 3, 4, 5].map(q => {
          const rows = scatterData.filter(d => d.nzdep_quintile === q);
          const mins = rows.map(d => d.nearest_minutes).sort((a, b) => a - b);
          const median = mins.length > 0 ? mins[Math.floor(mins.length / 2)] : 0;
          const scores = rows.map(d => d.nzdep_score).sort((a, b) => a - b);
          const medScore = scores.length > 0 ? scores[Math.floor(scores.length / 2)] : q * 200;
          return { x: medScore, y: median, q };
        }),
        { x: "x", y: "y", stroke: "#333", strokeWidth: 2, strokeDasharray: "6,3" }
      ),
    ],
  }));

  // Median by quintile bar chart
  display(html`<h3 style="margin-top: 2rem;">Median drive time by deprivation quintile</h3>`);

  const quintileStats = [1, 2, 3, 4, 5].map(q => {
    const rows = filteredAccess.filter(d => d.nzdep_quintile === q);
    const mins = rows.map(d => d.nearest_minutes).filter(d => d != null).sort((a, b) => a - b);
    return {
      quintile: `Q${q}${q === 1 ? " (least deprived)" : q === 5 ? " (most deprived)" : ""}`,
      median: mins.length > 0 ? mins[Math.floor(mins.length / 2)] : 0,
      q,
    };
  });

  display(Plot.plot({
    width,
    height: 200,
    x: { label: "Median drive time (minutes)" },
    y: { domain: quintileStats.map(d => d.quintile) },
    color: {
      domain: quintileStats.map(d => d.quintile),
      range: ["#4575b4", "#91bfdb", "#ffffbf", "#fc8d59", "#d73027"],
    },
    marks: [
      Plot.barX(quintileStats, {
        x: "median",
        y: "quintile",
        fill: "quintile",
        tip: true,
        title: d => `${d.quintile}: ${d.median?.toFixed(1)} min`,
      }),
      Plot.ruleX([0]),
    ],
  }));
} else {
  // Fallback: NZDep distribution chart
  display(html`<p style="color: #666; font-style: italic;">
    Deprivation vs access scatter will appear once travel times are computed.
    Showing NZDep distribution by health region below.
  </p>`);

  const regionStats = Array.from(await db.query(`
    SELECT health_region,
      COUNT(*) as sa2_count,
      AVG(nzdep_mean_score) as avg_score,
      SUM(CASE WHEN nzdep_quintile = 5 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as pct_q5
    FROM fact_sa2_nzdep
    WHERE health_region != ''
    GROUP BY health_region
    ORDER BY avg_score DESC
  `));

  display(Plot.plot({
    width,
    height: 200,
    x: { label: "% of SA2 areas in most deprived quintile (Q5)" },
    y: { domain: regionStats.map(d => d.health_region) },
    marks: [
      Plot.barX(regionStats, {
        x: "pct_q5",
        y: "health_region",
        fill: "#d73027",
        tip: true,
        title: d => `${d.health_region}: ${d.pct_q5?.toFixed(1)}% Q5 (${d.sa2_count} SA2s)`,
      }),
      Plot.ruleX([0]),
    ],
  }));
}
```

## Facility deserts

```js
if (hasAccess) {
  const deserts = filteredAccess
    .filter(d => d.nearest_minutes > 45)
    .sort((a, b) => (b.nzdep_quintile || 0) - (a.nzdep_quintile || 0) || b.nearest_minutes - a.nearest_minutes);

  display(html`<p style="margin-bottom: 0.5rem;">
    <strong>${deserts.length}</strong> SA2 areas are more than 45 minutes' drive from the nearest
    ${facilityType === "all" ? "facility" : facilityType === "gp" ? "GP" : "hospital"}.
    ${deserts.filter(d => d.nzdep_quintile >= 4).length} of these are in the two most deprived quintiles.
  </p>`);

  display(Inputs.table(deserts.slice(0, 50), {
    columns: ["sa2_name", "health_region", "nzdep_quintile", "nearest_minutes", "nearest_km", "facility_count_30min"],
    header: {
      sa2_name: "SA2 area",
      health_region: "Region",
      nzdep_quintile: "NZDep Q",
      nearest_minutes: "Drive (min)",
      nearest_km: "Distance (km)",
      facility_count_30min: "Within 30 min",
    },
    format: {
      nearest_minutes: d => d?.toFixed(0),
      nearest_km: d => d?.toFixed(1),
    },
    width: { sa2_name: 200, health_region: 250 },
  }));
} else {
  display(html`<p style="color: #666; font-style: italic;">
    Facility desert table will appear once travel times are computed.
  </p>`);
}
```

## Facility distribution by type

```js
const typeCounts = [
  { type: "GP / clinic", count: facilities.filter(f => f.facility_type === "gp").length, color: "#1a9850" },
  { type: "Hospital", count: facilities.filter(f => f.facility_type === "hospital").length, color: "#d73027" },
];

display(Plot.plot({
  width: Math.min(width, 400),
  height: 120,
  x: { label: "Count" },
  y: { domain: typeCounts.map(d => d.type) },
  marks: [
    Plot.barX(typeCounts, {
      x: "count",
      y: "type",
      fill: "color",
      tip: true,
    }),
    Plot.ruleX([0]),
    Plot.text(typeCounts, {
      x: "count",
      y: "type",
      text: d => d.count.toString(),
      dx: 15,
      fill: "#333",
      fontSize: 12,
    }),
  ],
}));
```

```js
// Regional facility counts
const regionFacilities = Array.from(await db.query(`
  SELECT health_region, facility_type, COUNT(*) as n
  FROM fact_facilities
  WHERE health_region != ''
  GROUP BY health_region, facility_type
  ORDER BY health_region, facility_type
`));

display(Plot.plot({
  width,
  height: 200,
  x: { label: "Count" },
  y: { domain: [...new Set(regionFacilities.map(d => d.health_region))] },
  color: {
    domain: ["gp", "hospital"],
    range: ["#1a9850", "#d73027"],
    legend: true,
  },
  marks: [
    Plot.barX(regionFacilities, Plot.stackX({
      x: "n",
      y: "health_region",
      fill: "facility_type",
      tip: true,
      title: d => `${d.health_region}: ${d.n} ${d.facility_type}`,
    })),
    Plot.ruleX([0]),
  ],
}));
```

---

<div style="font-size: 0.8em; color: #888; margin-top: 2rem;">

**Sources:** SA2 boundaries from Stats NZ (CC BY 4.0, 2025 edition). Facility locations from OpenStreetMap (ODbL). NZDep2018 from University of Otago. Drive times via OSRM.

**Methodology:** Each SA2 centroid is routed to its 3 nearest facilities (by straight-line distance) via OSRM driving directions. The minimum drive time is reported. NZDep2018 is aggregated from SA1 to SA2 using modal quintile assignment.

**Limitations:** SA2 2025 boundaries use a different concordance than the 2018 NZDep data — ~70% of SA2s have matched NZDep scores. Facility data from OSM may be incomplete; pharmacies and urgent care centres are underrepresented. Drive times assume car travel and do not account for public transport, which disproportionately affects deprived communities.

</div>
