---
title: Spatial Access to Health Services
toc: false
---

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
const facilities = Array.from(await db.query(`
  SELECT name, facility_type, latitude, longitude, sa2_name, health_region
  FROM fact_facilities
`));

const accessData = Array.from(await db.query(`
  SELECT * FROM fact_access WHERE nearest_minutes IS NOT NULL
`));

const sa2Nzdep = Array.from(await db.query(`
  SELECT sa2_code, sa2_name, nzdep_mean_score, nzdep_quintile, health_region, sa1_count, population
  FROM fact_sa2_nzdep
  WHERE nzdep_quintile IS NOT NULL
`));

const popLookup = new Map(sa2Nzdep.map(d => [d.sa2_code, d.population || 0]));
const centroids = await FileAttachment("data/sa2-centroids.json").json();
const hasAccess = accessData.length > 0;
```

```js
// All controls in a single compact bar
const controlBar = (() => {
  const bar = document.createElement("div");
  bar.style.cssText = "display:flex;flex-wrap:wrap;gap:0.5rem 1.25rem;align-items:center;padding:0.6rem 0;margin-bottom:0.25rem;font-family:-apple-system,system-ui,sans-serif;font-size:0.8rem;";

  const makeLabel = (text) => {
    const l = document.createElement("span");
    l.textContent = text;
    l.style.cssText = "color:#888;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.05em;";
    return l;
  };

  // Facility type
  const sel = document.createElement("select");
  sel.style.cssText = "padding:0.25rem 0.5rem;border:1px solid #ddd;border-radius:3px;font-size:0.8rem;background:#fff;";
  for (const [label, val] of [["GPs","gp"],["Hospitals","hospital"],["All","all"]]) {
    const opt = document.createElement("option");
    opt.value = val; opt.textContent = label;
    if (val === "gp") opt.selected = true;
    sel.appendChild(opt);
  }
  const g1 = document.createElement("div");
  g1.style.cssText = "display:flex;align-items:center;gap:0.35rem;";
  g1.appendChild(makeLabel("Show"));
  g1.appendChild(sel);
  bar.appendChild(g1);

  // LISA toggle
  const lisa = document.createElement("label");
  lisa.style.cssText = "display:flex;align-items:center;gap:0.3rem;cursor:pointer;";
  const lisaCb = document.createElement("input");
  lisaCb.type = "checkbox";
  lisa.appendChild(lisaCb);
  const lisaT = document.createElement("span");
  lisaT.textContent = "LISA";
  lisaT.style.cssText = "font-size:0.78rem;";
  lisa.appendChild(lisaT);
  bar.appendChild(lisa);

  // Separator
  const sep = document.createElement("span");
  sep.textContent = "|";
  sep.style.cssText = "color:#ddd;margin:0 0.25rem;";
  bar.appendChild(sep);

  // Fuel slider
  const g2 = document.createElement("div");
  g2.style.cssText = "display:flex;align-items:center;gap:0.3rem;";
  g2.appendChild(makeLabel("Fuel"));
  const fuelR = document.createElement("input");
  fuelR.type = "range"; fuelR.min = "1"; fuelR.max = "3"; fuelR.step = "0.1"; fuelR.value = "1";
  fuelR.style.cssText = "width:80px;";
  const fuelV = document.createElement("span");
  fuelV.textContent = "1\u00d7";
  fuelV.style.cssText = "min-width:2em;font-size:0.78rem;font-variant-numeric:tabular-nums;";
  fuelR.addEventListener("input", () => { fuelV.textContent = fuelR.value + "\u00d7"; });
  g2.appendChild(fuelR);
  g2.appendChild(fuelV);
  bar.appendChild(g2);

  // Telehealth toggle
  const th = document.createElement("label");
  th.style.cssText = "display:flex;align-items:center;gap:0.3rem;cursor:pointer;";
  const thCb = document.createElement("input");
  thCb.type = "checkbox";
  th.appendChild(thCb);
  const thT = document.createElement("span");
  thT.textContent = "Telehealth";
  thT.style.cssText = "font-size:0.78rem;";
  th.appendChild(thT);
  bar.appendChild(th);

  // Remove facilities slider
  const g3 = document.createElement("div");
  g3.style.cssText = "display:flex;align-items:center;gap:0.3rem;";
  g3.appendChild(makeLabel("Remove"));
  const remR = document.createElement("input");
  remR.type = "range"; remR.min = "0"; remR.max = "50"; remR.step = "5"; remR.value = "0";
  remR.style.cssText = "width:70px;";
  const remV = document.createElement("span");
  remV.textContent = "0%";
  remV.style.cssText = "min-width:2.5em;font-size:0.78rem;font-variant-numeric:tabular-nums;";
  remR.addEventListener("input", () => { remV.textContent = remR.value + "%"; });
  g3.appendChild(remR);
  g3.appendChild(remV);
  bar.appendChild(g3);

  // Wire up value getter
  bar.value = {
    facilityType: "gp", showLISA: false,
    fuelMultiplier: 1, telehealthOn: false, pandemicPct: 0,
  };

  const dispatch = () => {
    bar.value = {
      facilityType: sel.value,
      showLISA: lisaCb.checked,
      fuelMultiplier: parseFloat(fuelR.value),
      telehealthOn: thCb.checked,
      pandemicPct: parseInt(remR.value),
    };
    bar.dispatchEvent(new Event("input", {bubbles: true}));
  };

  sel.addEventListener("change", dispatch);
  lisaCb.addEventListener("change", dispatch);
  fuelR.addEventListener("input", dispatch);
  thCb.addEventListener("change", dispatch);
  remR.addEventListener("input", dispatch);

  return bar;
})();

const controls = view(controlBar);
```

```js
const facilityType = controls.facilityType;
const showLISA = controls.showLISA;
const fuelMultiplier = controls.fuelMultiplier;
const telehealthOn = controls.telehealthOn;
const pandemicPct = controls.pandemicPct;
const telehealthCap = 15;
```

```js
const scenarioActive = fuelMultiplier !== 1 || telehealthOn || pandemicPct > 0;
const scenarioData = (() => {
  let d = accessData;
  if (pandemicPct > 0) d = removeFacilitiesByPercent(facilities, d, centroids, pandemicPct);
  if (fuelMultiplier !== 1) d = applyFuelMultiplier(d, fuelMultiplier, null);
  if (telehealthOn) d = applyTelehealthCap(d, telehealthCap, null);
  return d;
})();
const activeData = scenarioActive ? scenarioData : accessData;
const filteredAccess = facilityType === "all"
  ? activeData
  : activeData.filter(d => d.facility_type === facilityType);
```

```js
// TopoJSON decode + lookups
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

const nzdepLookup = new Map(sa2Nzdep.map(d => [d.sa2_code, d]));
const accessLookup = new Map();
for (const row of filteredAccess) {
  const existing = accessLookup.get(row.sa2_code);
  if (!existing || row.nearest_minutes < existing.nearest_minutes) {
    accessLookup.set(row.sa2_code, row);
  }
}

const gpAccess = filteredAccess.filter(d => d.facility_type === "gp" && d.nearest_minutes != null);
const nationalMedianGP = gpAccess.length > 0
  ? gpAccess.map(d => d.nearest_minutes).sort((a, b) => a - b)[Math.floor(gpAccess.length / 2)]
  : 0;
```

```js
{
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

  // Full-height map
  const container = document.createElement("div");
  container.id = "access-map";
  container.style.width = "100%";
  container.style.height = "55vh";
  container.style.minHeight = "350px";
  display(container);

  await new Promise(r => setTimeout(r, 200));

  const map = L.map(container, { zoomSnap: 0.25, zoomControl: false }).setView([-41.3, 173.0], 5.5);
  L.control.zoom({ position: "bottomright" }).addTo(map);
  setTimeout(() => map.invalidateSize(), 300);

  L.tileLayer("https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png", {
    attribution: '\u00a9 OSM \u00a9 CARTO',
    subdomains: "abcd",
    maxZoom: 15,
  }).addTo(map);

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
      if (nz) parts.push("NZDep Q" + nz.nzdep_quintile + " (score: " + (nz.nzdep_mean_score?.toFixed(1) ?? "—") + ")");
      if (access) parts.push(access.nearest_minutes?.toFixed(0) + " min to nearest " + access.facility_type);
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

  for (const f of filteredFacilities) {
    if (f.latitude == null || f.longitude == null) continue;
    L.circleMarker([f.latitude, f.longitude], {
      radius: f.facility_type === "hospital" ? 4 : 2.5,
      fillColor: f.facility_type === "hospital" ? "#7b3294" : "#008837",
      color: "#fff",
      weight: 0.5,
      fillOpacity: 0.85,
    })
    .bindTooltip(f.name + " (" + f.facility_type + ")")
    .bindPopup(() => buildFacilityPopup(f, nzdepLookup, centroids), { maxWidth: 280 })
    .addTo(map);
  }

  // Compact legend
  const legendEl = document.createElement("div");
  legendEl.style.cssText = "background:rgba(255,255,255,0.9);backdrop-filter:blur(4px);padding:6px 8px;border-radius:4px;font-size:10px;line-height:1.6;box-shadow:0 1px 4px rgba(0,0,0,0.2);";
  const swatchFn = (c) => '<span style="display:inline-block;width:12px;height:8px;background:' + c + ';margin-right:3px;vertical-align:middle;"></span>';
  const dotFn = (c) => '<span style="display:inline-block;width:6px;height:6px;background:' + c + ';border-radius:50%;margin-right:3px;vertical-align:middle;"></span>';
  const lines = [];
  if (hasAccess) {
    lines.push("<b>Drive time</b>");
    for (const [v, l] of [[3,"<5"],[12,"5-15"],[25,"15-30"],[37,"30-45"],[65,"60+"]]) lines.push(swatchFn(travelColor(v)) + l);
  }
  lines.push(dotFn("#008837") + "GP " + dotFn("#7b3294") + "Hospital");
  legendEl.innerHTML = lines.join("<br>");
  const LegendControl = L.Control.extend({ onAdd() { return legendEl; } });
  new LegendControl({ position: "bottomright" }).addTo(map);

  window._sa2Layer = sa2Layer;
}
```

```js
// Key finding — one sentence + the quintile chart
if (hasAccess) {
  const byQuintile = [1, 2, 3, 4, 5].map(q => {
    const rows = filteredAccess.filter(d => d.nzdep_quintile === q);
    const mins = rows.filter(d => d.nearest_minutes != null).map(d => d.nearest_minutes);
    const wts = rows.filter(d => d.nearest_minutes != null).map(d => popLookup.get(d.sa2_code) || 1);
    const totalPop = wts.reduce((s, w) => s + w, 0);
    const popOver30 = rows.filter(d => d.nearest_minutes > 30).reduce((s, d) => s + (popLookup.get(d.sa2_code) || 0), 0);
    return {
      quintile: "Q" + q + (q === 1 ? " least deprived" : q === 5 ? " most deprived" : ""),
      median: weightedMedian(mins, wts),
      pctOver30: totalPop > 0 ? (popOver30 / totalPop * 100) : 0,
      q,
    };
  });
  const q5Over30 = byQuintile[4]?.pctOver30;
  const q1Over30 = byQuintile[0]?.pctOver30;

  display(html`<p style="font-size:1.1rem;max-width:640px;margin:1.5rem 0 0.5rem;">
    <strong style="color:#c4391d;">${q5Over30?.toFixed(0)}%</strong> of people in the most deprived areas are 30+ minutes from a GP, vs <strong>${q1Over30?.toFixed(0)}%</strong> in the least deprived. The medians look similar — the disparity is in the tail.
  </p>`);

  display(Plot.plot({
    width,
    height: 160,
    marginLeft: 140,
    x: { label: "Median drive time (minutes)" },
    y: { domain: byQuintile.map(d => d.quintile) },
    color: {
      domain: byQuintile.map(d => d.quintile),
      range: ["#4575b4", "#91bfdb", "#ffffbf", "#fc8d59", "#d73027"],
    },
    marks: [
      Plot.barX(byQuintile, {
        x: "median",
        y: "quintile",
        fill: "quintile",
        tip: true,
        title: d => d.quintile + ": " + d.median?.toFixed(1) + " min, " + d.pctOver30.toFixed(0) + "% over 30 min",
      }),
      Plot.ruleX([0]),
    ],
  }));
}
```

```js
// Scenario impact — only shows when active
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
        <div class="impact-label">people affected</div>
      </div>
      <div>
        <div class="impact-value">${diff.sa2sCrossed}</div>
        <div class="impact-label">SA2s crossing 30-min line</div>
      </div>
      <div>
        <div class="impact-value" style="color: ${medianDelta > 0 ? "#d73027" : medianDelta < 0 ? "#4575b4" : "#333"};">${medianDelta > 0 ? "+" : ""}${medianDelta.toFixed(1)} min</div>
        <div class="impact-label">median change</div>
      </div>
    </div>
  `);
}
```

```js
// Facility deserts — the actionable table
if (hasAccess) {
  const deserts = filteredAccess
    .filter(d => d.nearest_minutes > 45)
    .sort((a, b) => (b.nzdep_quintile || 0) - (a.nzdep_quintile || 0) || b.nearest_minutes - a.nearest_minutes);

  if (deserts.length > 0) {
    display(html`<h2 style="margin-top:2rem;">Facility deserts</h2>`);
    display(html`<p style="font-size:0.9rem;color:#555;">
      <strong>${deserts.length}</strong> SA2 areas are 45+ min from the nearest ${facilityType === "gp" ? "GP" : facilityType === "hospital" ? "hospital" : "facility"}.
      ${deserts.filter(d => d.nzdep_quintile >= 4).length} are in the most deprived quintiles.
    </p>`);

    display(Inputs.table(deserts.slice(0, 20), {
      columns: ["sa2_name", "health_region", "nzdep_quintile", "nearest_minutes", "facility_count_30min"],
      header: {
        sa2_name: "Area",
        health_region: "Region",
        nzdep_quintile: "NZDep Q",
        nearest_minutes: "Drive (min)",
        facility_count_30min: "Within 30 min",
      },
      format: {
        nearest_minutes: d => d?.toFixed(0),
      },
    }));
  }
}
```

```js
// LISA — compute when toggled
{
  if (showLISA && hasAccess) {
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
    display(html`<p style="font-size:0.85rem;color:#555;"><strong>${hhCount}</strong> hotspots (structurally underserved), <strong>${llCount}</strong> coldspots (well-served).</p>`);
  } else if (!showLISA && window._sa2Layer) {
    window._sa2Layer.eachLayer(layer => {
      if (layer.feature?.properties) layer.feature.properties._lisaCategory = "ns";
      layer.setStyle({ weight: 0.3, color: "#666", dashArray: null, opacity: 0.4 });
    });
  }
}
```

<details class="details-panel">
<summary>Analyst tools — CSV export, summary statistics, scatter plot</summary>

```js
{
  const exportBtn = document.createElement("button");
  exportBtn.textContent = "Download SA2 access data (CSV)";
  exportBtn.style.cssText = "padding: 0.5rem 1rem; border-radius: 4px; border: 1px solid #ccc; background: #fff; cursor: pointer; font-size: 0.85em;";
  exportBtn.addEventListener("click", () => {
    const header = "sa2_code,sa2_name,nzdep_quintile,nzdep_score,health_region,nearest_gp_minutes,nearest_hospital_minutes";
    const gpLk = new Map();
    const hospLk = new Map();
    for (const r of accessData) {
      if (r.facility_type === "gp") { const ex = gpLk.get(r.sa2_code); if (!ex || r.nearest_minutes < ex.nearest_minutes) gpLk.set(r.sa2_code, r); }
      else if (r.facility_type === "hospital") { const ex = hospLk.get(r.sa2_code); if (!ex || r.nearest_minutes < ex.nearest_minutes) hospLk.set(r.sa2_code, r); }
    }
    const rows = sa2Nzdep.map(d => {
      const gp = gpLk.get(d.sa2_code);
      const hosp = hospLk.get(d.sa2_code);
      const esc = (s) => (s || "").includes(",") ? '"' + s + '"' : s;
      return [d.sa2_code, esc(d.sa2_name), d.nzdep_quintile, d.nzdep_mean_score?.toFixed(1) ?? "", esc(d.health_region), gp?.nearest_minutes?.toFixed(1) ?? "", hosp?.nearest_minutes?.toFixed(1) ?? ""].join(",");
    });
    const csv = [header, ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "nz_sa2_access_data.csv"; a.click();
    URL.revokeObjectURL(url);
  });
  display(exportBtn);
}
```

```js
if (hasAccess) {
  const scatterData = filteredAccess.filter(d => d.nzdep_score != null && d.nearest_minutes != null);
  display(Plot.plot({
    width,
    height: 350,
    x: { label: "NZDep2018 deprivation score", nice: true },
    y: { label: "Minutes to nearest facility", nice: true },
    color: {
      domain: ["Northern | Te Tai Tokerau", "Midland | Te Manawa Taki", "Central | Te Ikaroa", "South Island | Te Waipounamu"],
      range: ["#e69f00", "#56b4e9", "#009e73", "#cc79a7"],
      legend: true,
    },
    marks: [
      Plot.dot(scatterData, { x: "nzdep_score", y: "nearest_minutes", fill: "health_region", r: 2, opacity: 0.4, tip: true }),
    ],
  }));
}
```

```js
if (hasAccess) {
  const allMins = filteredAccess.filter(d => d.nearest_minutes != null).map(d => d.nearest_minutes);
  const allWeights = filteredAccess.filter(d => d.nearest_minutes != null).map(d => popLookup.get(d.sa2_code) || 1);
  const wMed = weightedMedian(allMins, allWeights);
  const p90 = weightedPercentile(allMins, allWeights, 0.90);
  const giniVal = gini(allMins, allWeights);
  const totalPop = allWeights.reduce((s, w) => s + w, 0);
  const within30 = allMins.reduce((s, v, i) => s + (v <= 30 ? allWeights[i] : 0), 0);
  display(Inputs.table([
    { Stat: "Weighted median", Value: (wMed?.toFixed(1) ?? "—") + " min" },
    { Stat: "P90", Value: (p90?.toFixed(1) ?? "—") + " min" },
    { Stat: "Within 30 min", Value: (within30 / totalPop * 100).toFixed(1) + "%" },
    { Stat: "Gini coefficient", Value: giniVal.toFixed(3) },
  ]));
}
```

</details>

<div class="methodology">

**Sources.** SA2 boundaries: Stats NZ (CC BY 4.0, 2025). Facilities: OpenStreetMap (ODbL). NZDep2018: University of Otago.

**Method.** Haversine estimation with 1.4 winding factor (35 km/h urban, 55 km/h rural). NZDep2018 aggregated SA1→SA2 using modal quintile. ~70% SA2 concordance between 2025 and 2018 boundaries.

**Caveats.** Car travel only — no public transport. Ecological fallacy applies. Spatially autocorrelated (Moran's I accounts for this).

</div>
