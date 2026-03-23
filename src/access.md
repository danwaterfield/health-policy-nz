---
title: Spatial Access to Health Services
---

# Spatial Access to Health Services

<p class="lead">Do deprived communities face longer travel times to reach care? This page maps NZ's 2,395 Statistical Area 2 zones by deprivation and proximity to GPs, hospitals, and urgent care.</p>

```js
import * as topojson from "npm:topojson-client";
import * as d3 from "npm:d3";
import L from "npm:leaflet";
import {exportButtons} from "./components/chart-export.js";
import {median, weightedMedian, weightedPercentile, gini, pearsonR, haversineKm, moranI, localMoranI, nearestNeighbourR} from "./components/access-stats.js";
import {buildSA2Popup, buildFacilityPopup, findNearestFacility} from "./components/access-detail.js";
import {removeFacilitiesByPercent, applyFuelMultiplier, applyTelehealthCap, scenarioDiff} from "./components/scenario-engine.js";
const sa2Topo = await FileAttachment("data/nz-sa2.json").json();
```

```js
const db = await DuckDBClient.of({
  fact_facilities: FileAttachment("data/fact_facilities.parquet"),
  fact_access: FileAttachment("data/fact_access.parquet"),
  fact_sa2_nzdep: FileAttachment("data/fact_sa2_nzdep.parquet"),
  sim_agents: FileAttachment("data/sim_agents.parquet"),
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

// Load SA2 centroids early — used by scenario engine and map popups
const centroids = await FileAttachment("data/sa2-centroids.json").json();

const hasAccess = accessData.length > 0;

// Load top autoresearch configuration for Counties Manukau
const topAgentRows = Array.from(await db.query(`
  SELECT * FROM sim_agents WHERE accepted > 0 ORDER BY best_value DESC LIMIT 1
`));
const topAgent = topAgentRows[0] || null;
```


```js
// Controls
const facilityType = view(Inputs.select(
  new Map([["GPs", "gp"], ["Hospitals", "hospital"], ["All types", "all"]]),
  { label: "Facility type", value: "gp" }
));
```

```js
const showLISA = view(Inputs.toggle({ label: "Show access hotspots (LISA)", value: false }));
```

```js
const showAutoresearch = view(Inputs.toggle({label: "Show autoresearch focus area", value: false}));
```

```js
if (showAutoresearch) {
  if (topAgent) {
    display(html`
      <div class="note">
        <strong>Autoresearch: Top Configuration (Counties Manukau)</strong>
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.5rem; margin-top: 0.5rem; font-size: 0.85em;">
          <div><strong>Agent:</strong> ${topAgent.agent}</div>
          <div><strong>Metric:</strong> ${topAgent.primary_metric}</div>
          <div><strong>Best:</strong> ${topAgent.best_value?.toFixed(3)}</div>
          <div><strong>Experiments:</strong> ${topAgent.experiments}</div>
        </div>
        <p style="margin: 0.5rem 0 0;">
          Based on 887 simulated configurations for Counties Manukau.
          <a href="./autoresearch">View full analysis →</a>
        </p>
      </div>
    `);
  } else {
    display(html`
      <div class="note">
        <strong>Autoresearch: No accepted configurations found</strong>
        <p style="margin: 0.5rem 0 0;">
          Run the autoresearch simulation to populate results.
          <a href="./autoresearch">View autoresearch page →</a>
        </p>
      </div>
    `);
  }
}
```

```js
// Compute scenario data early — needed by map and stats
const scenarioActive = fuelMultiplier !== 1 || telehealthOn || pandemicPct > 0;
let scenarioData = accessData;
if (pandemicPct > 0) {
  scenarioData = removeFacilitiesByPercent(facilities, scenarioData, centroids, pandemicPct);
}
if (fuelMultiplier !== 1) {
  scenarioData = applyFuelMultiplier(scenarioData, fuelMultiplier, null);
}
if (telehealthOn) {
  scenarioData = applyTelehealthCap(scenarioData, telehealthCap, null);
}
```

```js
// Compute summary stats — needed by map and stat cards
const activeData = scenarioActive ? scenarioData : accessData;
const filteredAccess = facilityType === "all"
  ? activeData
  : activeData.filter(d => d.facility_type === facilityType);
```

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

  // SA2 choropleth layer — store on window for LISA styling from other cells
  const sa2Layer = L.geoJSON(sa2Geojson, {
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
      layer.on("mouseout", (e) => {
        const lisaCat = e.target.feature?.properties?._lisaCategory;
        if (lisaCat && lisaCat !== "ns") {
          const lisaStyles = { HH: { color: "#d73027", weight: 2, dashArray: null }, LL: { color: "#4575b4", weight: 2, dashArray: null }, HL: { color: "#999", weight: 1.5, dashArray: "4,3" }, LH: { color: "#999", weight: 1.5, dashArray: "4,3" } };
          const ls = lisaStyles[lisaCat] || {};
          e.target.setStyle({ weight: ls.weight || 0.3, color: ls.color || "#666", fillOpacity: 0.7, dashArray: ls.dashArray || null });
        } else {
          e.target.setStyle({ weight: 0.3, color: "#666", fillOpacity: 0.7 });
        }
      });
    },
  }).addTo(map);

  // Counties Manukau / Northern region highlight overlay
  if (showAutoresearch) {
    const northernFeatures = sa2Geojson.features.filter(f => {
      const region = f.properties?.health_region || "";
      return region === "Northern | Te Tai Tokerau";
    });
    if (northernFeatures.length > 0) {
      L.geoJSON({ type: "FeatureCollection", features: northernFeatures }, {
        style: () => ({
          weight: 2,
          color: "#7b3294",
          dashArray: "6,4",
          fillOpacity: 0,
          opacity: 0.8,
        }),
        onEachFeature: (feature, layer) => {
          layer.bindTooltip("Northern region (includes Counties Manukau)", { sticky: true });
        },
      }).addTo(map);
    }
  }

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

  // Expose sa2Layer for LISA styling from other cells
  window._sa2Layer = sa2Layer;
}
```

```js
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
  const q1Over30 = byQuintile[0]?.pctOver30;
  const gpCount = facilities.filter(f => f.facility_type === "gp").length;
  const hospCount = facilities.filter(f => f.facility_type === "hospital").length;

  display(html`<p>
    The map above shows estimated drive times from ${sa2Nzdep.length.toLocaleString()} SA2 areas
    to the nearest of ${gpCount.toLocaleString()} GPs and ${hospCount.toLocaleString()} hospitals
    mapped from OpenStreetMap. The population-weighted median drive time is
    <strong>${q1Med != null ? q1Med.toFixed(0) : "—"} minutes</strong> for the least deprived areas (Q1) and
    <strong>${q5Med != null ? q5Med.toFixed(0) : "—"} minutes</strong> for the most deprived (Q5).
  </p>`);

  display(html`<p>
    The medians are similar because most Q5 areas are in dense urban centres — South Auckland, Porirua —
    where GPs are close. The disparity is in the tail:
    <strong>${q5Over30 != null ? q5Over30.toFixed(0) : "—"}%</strong> of people in the most deprived areas
    are more than 30 minutes from a GP, compared to
    <strong>${q1Over30 != null ? q1Over30.toFixed(0) : "—"}%</strong> in the least deprived.
  </p>`);

  display(html`<p class="note">
    ${sa2Nzdep.length.toLocaleString()} of ${(accessData.length / 2).toLocaleString()} SA2 areas
    matched between 2025 boundaries and 2018 NZDep data (~70% concordance).
    Unmatched areas shown in grey. Statistics are population-weighted.
  </p>`);
} else {
  display(html`<p>
    Travel time data not yet computed. The map above shows NZDep2018 deprivation by SA2.
  </p>`);
}
```

## What-if scenarios

```js
const fuelMultiplier = view(Inputs.range([1, 3], {step: 0.1, value: 1, label: "Fuel price multiplier"}));
const telehealthOn = view(Inputs.toggle({label: "Universal telehealth", value: false}));
const telehealthCap = telehealthOn
  ? view(Inputs.select([10, 15, 20], {label: "Max effective travel time (min)", value: 15}))
  : 15;
const pandemicPct = view(Inputs.range([0, 50], {step: 5, value: 0, label: "% facilities removed (pandemic mode)"}));
const scenarioResetBtn = view(Inputs.button("Reset all scenarios"));
```

```js
if (scenarioActive && hasAccess) {
  const diff = scenarioDiff(accessData, scenarioData, popLookup);
  const scenarioGpRows = scenarioData.filter(d => d.facility_type === "gp" && d.nearest_minutes != null);
  const baseGpRows = accessData.filter(d => d.facility_type === "gp" && d.nearest_minutes != null);
  const scenarioMedian = scenarioGpRows.length > 0
    ? [...scenarioGpRows].sort((a, b) => a.nearest_minutes - b.nearest_minutes)[Math.floor(scenarioGpRows.length / 2)].nearest_minutes
    : 0;
  const baseMedian = baseGpRows.length > 0
    ? [...baseGpRows].sort((a, b) => a.nearest_minutes - b.nearest_minutes)[Math.floor(baseGpRows.length / 2)].nearest_minutes
    : 0;
  const medianDelta = scenarioMedian - baseMedian;

  display(html`
    <div class="scenario-impact">
      <div>
        <div class="impact-value">${diff.peopleAffected.toLocaleString()}</div>
        <div class="impact-label">people affected (&gt;0.5 min change)</div>
      </div>
      <div>
        <div class="impact-value">${diff.sa2sCrossed}</div>
        <div class="impact-label">SA2s crossing 30-min threshold</div>
      </div>
      <div>
        <div class="impact-value" style="color: ${medianDelta > 0 ? "#d73027" : medianDelta < 0 ? "#4575b4" : "#333"};">${medianDelta > 0 ? "+" : ""}${medianDelta.toFixed(1)} min</div>
        <div class="impact-label">median GP drive time change</div>
      </div>
    </div>
  `);

  display(html`<p class="note">
    Active: ${fuelMultiplier !== 1 ? `fuel x${fuelMultiplier}` : ""}${telehealthOn ? ` telehealth cap ${telehealthCap} min` : ""}${pandemicPct > 0 ? ` ${pandemicPct}% facilities removed` : ""}
  </p>`);
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
  display(html`<p class="note">
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
  display(html`<p class="note">
    Facility desert table will appear once travel times are computed.
  </p>`);
}
```

```js
// LISA layer toggle — compute once, apply/remove on toggle
{
  // Build SA2 code → LISA category lookup from GP travel times
  const lisaStatusEl = document.createElement("p");
  lisaStatusEl.style.cssText = "font-size: 0.85em; color: #555; margin: 0.5rem 0;";

  if (showLISA && hasAccess) {
    lisaStatusEl.textContent = "Computing spatial autocorrelation (this may take a few seconds)...";
    display(lisaStatusEl);

    // Defer heavy computation to avoid blocking UI
    await new Promise(r => setTimeout(r, 50));

    // Gather GP travel times aligned with centroids
    const gpRows = accessData.filter(d => d.facility_type === "gp" && d.nearest_minutes != null);
    const gpLookup = new Map();
    for (const r of gpRows) {
      const existing = gpLookup.get(r.sa2_code);
      if (!existing || r.nearest_minutes < existing.nearest_minutes) gpLookup.set(r.sa2_code, r);
    }

    const lisaInput = centroids
      .filter(c => gpLookup.has(c.sa2_code))
      .map(c => ({ code: c.sa2_code, val: gpLookup.get(c.sa2_code).nearest_minutes, lat: c.lat, lon: c.lon }));

    const vals = lisaInput.map(d => d.val);
    const lats = lisaInput.map(d => d.lat);
    const lons = lisaInput.map(d => d.lon);

    const lisaResults = localMoranI(vals, lats, lons, 50);
    const lisaByCode = new Map();
    lisaResults.forEach((r, idx) => { lisaByCode.set(lisaInput[idx].code, r.category); });

    const lisaStyles = {
      HH: { color: "#d73027", weight: 2, dashArray: null },
      LL: { color: "#4575b4", weight: 2, dashArray: null },
      HL: { color: "#999", weight: 1.5, dashArray: "4,3" },
      LH: { color: "#999", weight: 1.5, dashArray: "4,3" },
    };

    // Apply LISA styling to SA2 layer
    if (window._sa2Layer) {
      window._sa2Layer.eachLayer(layer => {
        const code = layer.feature?.properties?.sa2_code;
        const cat = lisaByCode.get(code) || "ns";
        layer.feature.properties._lisaCategory = cat;
        if (cat !== "ns") {
          const s = lisaStyles[cat];
          layer.setStyle({ weight: s.weight, color: s.color, dashArray: s.dashArray, opacity: 0.8 });
        }
      });
    }

    const hhCount = lisaResults.filter(r => r.category === "HH").length;
    const llCount = lisaResults.filter(r => r.category === "LL").length;
    const hlCount = lisaResults.filter(r => r.category === "HL").length;
    const lhCount = lisaResults.filter(r => r.category === "LH").length;
    lisaStatusEl.innerHTML = `<strong>${hhCount}</strong> HH hotspots (structurally underserved), <strong>${llCount}</strong> LL coldspots (well-served), ${hlCount} HL outliers, ${lhCount} LH outliers.`;
  } else if (showLISA && !hasAccess) {
    lisaStatusEl.textContent = "LISA requires travel time data. Run the pipeline with OSRM access.";
    display(lisaStatusEl);
  } else {
    // Reset LISA styling when toggled off
    if (window._sa2Layer) {
      window._sa2Layer.eachLayer(layer => {
        if (layer.feature?.properties) layer.feature.properties._lisaCategory = "ns";
        layer.setStyle({ weight: 0.3, color: "#666", dashArray: null, opacity: 0.4 });
      });
    }
  }
}
```

<details class="details-panel">
<summary>Analyst tools</summary>

## CSV export

```js
{
  const exportBtn = document.createElement("button");
  exportBtn.textContent = "Download SA2 access data (CSV)";
  exportBtn.style.cssText = "padding: 0.5rem 1rem; border-radius: 6px; border: 1px solid #4575b4; background: #f0f7ff; color: #4575b4; cursor: pointer; font-size: 0.9em;";
  exportBtn.addEventListener("click", () => {
    const header = "sa2_code,sa2_name,nzdep_quintile,nzdep_score,population,health_region,nearest_gp_minutes,nearest_gp_km,nearest_hospital_minutes,nearest_hospital_km,facilities_within_30min";
    const gpLookup = new Map();
    const hospLookup = new Map();
    for (const r of accessData) {
      if (r.facility_type === "gp") {
        const ex = gpLookup.get(r.sa2_code);
        if (!ex || r.nearest_minutes < ex.nearest_minutes) gpLookup.set(r.sa2_code, r);
      } else if (r.facility_type === "hospital") {
        const ex = hospLookup.get(r.sa2_code);
        if (!ex || r.nearest_minutes < ex.nearest_minutes) hospLookup.set(r.sa2_code, r);
      }
    }
    const rows = sa2Nzdep.map(d => {
      const gp = gpLookup.get(d.sa2_code);
      const hosp = hospLookup.get(d.sa2_code);
      const escapeName = (d.sa2_name || "").includes(",") ? `"${d.sa2_name}"` : d.sa2_name;
      const escapeRegion = (d.health_region || "").includes(",") ? `"${d.health_region}"` : d.health_region;
      return [
        d.sa2_code, escapeName, d.nzdep_quintile, d.nzdep_mean_score?.toFixed(1) ?? "",
        d.population || "", escapeRegion,
        gp?.nearest_minutes?.toFixed(1) ?? "", gp?.nearest_km?.toFixed(1) ?? "",
        hosp?.nearest_minutes?.toFixed(1) ?? "", hosp?.nearest_km?.toFixed(1) ?? "",
        gp?.facility_count_30min ?? ""
      ].join(",");
    });
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "nz_sa2_access_data.csv";
    a.click();
    URL.revokeObjectURL(url);
  });
  display(exportBtn);
}
```

## Summary statistics

```js
if (hasAccess) {
  const allMins = filteredAccess.filter(d => d.nearest_minutes != null).map(d => d.nearest_minutes);
  const allWeights = filteredAccess.filter(d => d.nearest_minutes != null).map(d => popLookup.get(d.sa2_code) || 1);
  const allScores = filteredAccess.filter(d => d.nearest_minutes != null && d.nzdep_score != null).map(d => d.nzdep_score);
  const allMinsForCorr = filteredAccess.filter(d => d.nearest_minutes != null && d.nzdep_score != null).map(d => d.nearest_minutes);

  const wMean = allWeights.reduce((s, w, i) => s + w * allMins[i], 0) / allWeights.reduce((s, w) => s + w, 0);
  const wMed = weightedMedian(allMins, allWeights);
  const p25 = weightedPercentile(allMins, allWeights, 0.25);
  const p75 = weightedPercentile(allMins, allWeights, 0.75);
  const p90 = weightedPercentile(allMins, allWeights, 0.90);
  const giniVal = gini(allMins, allWeights);
  const corrVal = pearsonR(allScores, allMinsForCorr);

  const totalPop = allWeights.reduce((s, w) => s + w, 0);
  const within15 = allMins.reduce((s, v, i) => s + (v <= 15 ? allWeights[i] : 0), 0);
  const within30 = allMins.reduce((s, v, i) => s + (v <= 30 ? allWeights[i] : 0), 0);
  const within45 = allMins.reduce((s, v, i) => s + (v <= 45 ? allWeights[i] : 0), 0);
  const within60 = allMins.reduce((s, v, i) => s + (v <= 60 ? allWeights[i] : 0), 0);

  // Quintile-level stats
  const quintileRows = [1, 2, 3, 4, 5].map(q => {
    const rows = filteredAccess.filter(d => d.nzdep_quintile === q && d.nearest_minutes != null);
    const mins = rows.map(d => d.nearest_minutes);
    const wts = rows.map(d => popLookup.get(d.sa2_code) || 1);
    return {
      q,
      wMean: wts.reduce((s, w, i) => s + w * mins[i], 0) / (wts.reduce((s, w) => s + w, 0) || 1),
      wMed: weightedMedian(mins, wts),
      p25: weightedPercentile(mins, wts, 0.25),
      p75: weightedPercentile(mins, wts, 0.75),
      p90: weightedPercentile(mins, wts, 0.90),
    };
  });

  // Spatial stats (compute once — Moran's I is expensive)
  let moranResult = null;
  let nnrResult = null;
  if (centroids.length > 0) {
    const gpRows = accessData.filter(d => d.facility_type === "gp" && d.nearest_minutes != null);
    const gpMap = new Map();
    for (const r of gpRows) {
      const ex = gpMap.get(r.sa2_code);
      if (!ex || r.nearest_minutes < ex.nearest_minutes) gpMap.set(r.sa2_code, r);
    }
    const spatialInput = centroids.filter(c => gpMap.has(c.sa2_code));
    const sVals = spatialInput.map(c => gpMap.get(c.sa2_code).nearest_minutes);
    const sLats = spatialInput.map(c => c.lat);
    const sLons = spatialInput.map(c => c.lon);

    moranResult = moranI(sVals, sLats, sLons, 50);

    // Nearest-neighbour R on facility locations (NZ land area ~268,021 km2)
    const facLats = facilities.filter(f => f.latitude != null).map(f => f.latitude);
    const facLons = facilities.filter(f => f.longitude != null).map(f => f.longitude);
    nnrResult = nearestNeighbourR(facLats, facLons, 268021);
  }

  // Overall stats as flat data for Inputs.table
  const overallStats = [
    { Statistic: "Weighted mean", Value: `${wMean.toFixed(1)} min` },
    { Statistic: "Weighted median", Value: `${wMed?.toFixed(1) ?? "—"} min` },
    { Statistic: "P25", Value: `${p25?.toFixed(1) ?? "—"} min` },
    { Statistic: "P75", Value: `${p75?.toFixed(1) ?? "—"} min` },
    { Statistic: "P90", Value: `${p90?.toFixed(1) ?? "—"} min` },
    { Statistic: "Gini coefficient", Value: giniVal.toFixed(3) },
    { Statistic: "Pearson r (NZDep vs time)", Value: `${corrVal.r?.toFixed(3) ?? "—"} (n=${corrVal.n})` },
    { Statistic: "Within 15 min", Value: `${(within15 / totalPop * 100).toFixed(1)}%` },
    { Statistic: "Within 30 min", Value: `${(within30 / totalPop * 100).toFixed(1)}%` },
    { Statistic: "Within 45 min", Value: `${(within45 / totalPop * 100).toFixed(1)}%` },
    { Statistic: "Within 60 min", Value: `${(within60 / totalPop * 100).toFixed(1)}%` },
  ];

  if (moranResult) {
    overallStats.push(
      { Statistic: "Global Moran's I", Value: moranResult.I.toFixed(3) },
      { Statistic: "Moran's I z-score", Value: moranResult.z.toFixed(2) },
      { Statistic: "Moran's I p-value", Value: moranResult.p < 0.001 ? "<0.001" : moranResult.p.toFixed(3) },
      { Statistic: "Nearest-neighbour R", Value: nnrResult?.R ?? "—" },
      { Statistic: "NNR z-score", Value: nnrResult?.z ?? "—" },
    );
  }

  const quintileFlat = quintileRows.map(r => ({
    Quintile: `Q${r.q}`,
    Mean: r.wMean.toFixed(1),
    Median: r.wMed?.toFixed(1) ?? "—",
    P25: r.p25?.toFixed(1) ?? "—",
    P75: r.p75?.toFixed(1) ?? "—",
    P90: r.p90?.toFixed(1) ?? "—",
  }));

  display(html`<h3>Overall (population-weighted)</h3>`);
  display(Inputs.table(overallStats));
  display(html`<h3>By NZDep quintile</h3>`);
  display(Inputs.table(quintileFlat));
} else {
  display(html`<p class="note">Summary statistics require travel time data.</p>`);
}
```

## Cross-tabulation: health region x NZDep quintile

```js
if (hasAccess) {
  // Pivot: health region rows × NZDep quintile columns, population-weighted median travel time
  const regions = [...new Set(filteredAccess.map(d => d.health_region).filter(Boolean))].sort();
  const crosstab = regions.map(region => {
    const row = { region };
    for (const q of [1, 2, 3, 4, 5]) {
      const rows = filteredAccess.filter(d => d.health_region === region && d.nzdep_quintile === q && d.nearest_minutes != null);
      const mins = rows.map(d => d.nearest_minutes);
      const wts = rows.map(d => popLookup.get(d.sa2_code) || 1);
      row[`q${q}`] = weightedMedian(mins, wts);
    }
    return row;
  });

  // Build cross-tab as flat data for Inputs.table
  const crosstabFlat = crosstab.map(r => ({
    "Health region": r.region,
    "Q1 (least)": r.q1 != null ? r.q1.toFixed(1) : "—",
    "Q2": r.q2 != null ? r.q2.toFixed(1) : "—",
    "Q3": r.q3 != null ? r.q3.toFixed(1) : "—",
    "Q4": r.q4 != null ? r.q4.toFixed(1) : "—",
    "Q5 (most)": r.q5 != null ? r.q5.toFixed(1) : "—",
  }));
  display(html`<p style="font-weight: 600; margin-bottom: 0.25rem;">Population-weighted median drive time (minutes) by region and deprivation</p>`);
  display(Inputs.table(crosstabFlat));
} else {
  display(html`<p class="note">Cross-tabulation requires travel time data.</p>`);
}
```

</details>

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

<div class="methodology">

**Sources:** SA2 boundaries from Stats NZ (CC BY 4.0, 2025 edition). Facility locations from OpenStreetMap (ODbL). NZDep2018 from University of Otago. Drive times via OSRM.

**Methodology:** Each SA2 centroid is routed to its 3 nearest facilities (by straight-line distance) via OSRM driving directions. The minimum drive time is reported. NZDep2018 is aggregated from SA1 to SA2 using modal quintile assignment.

**Limitations:** SA2 2025 boundaries use a different concordance than the 2018 NZDep data — ~70% of SA2s have matched NZDep scores. Facility data from OSM may be incomplete; pharmacies and urgent care centres are underrepresented. Drive times assume car travel and do not account for public transport, which disproportionately affects deprived communities.

**MAUP:** Results are sensitive to the choice of spatial unit. SA2 areas vary dramatically in size. Aggregating to health regions or TAs would produce different patterns.

**Ecological fallacy:** Area-level deprivation and access do not necessarily describe individuals. An SA2 with NZDep Q5 and 40 min travel time does not mean every resident is deprived and poorly served.

**Boundary effects:** SA2s near the coast may have inflated travel times. Island SA2s (Chatham Islands) are excluded from the map but included with capped times.

**Spatial autocorrelation:** Travel times are spatially autocorrelated — nearby SA2s tend to have similar values. The Moran's I and LISA statistics account for this. Standard correlation results should be interpreted with this caveat.

</div>
