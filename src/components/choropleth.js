/**
 * Choropleth map of NZ health regions.
 *
 * Expects a TopoJSON object loaded externally (via FileAttachment in the
 * calling .md page — FileAttachment is not available in imported JS modules).
 *
 * The TopoJSON contains 20 DHB features, each with a `health_region` property
 * mapping to one of the 4 NZHS health regions. Each DHB is coloured by its
 * parent region's equity gap value.
 *
 * Colour: RdYlBu reversed (red = adverse, blue = favourable).
 * Accessibility: colour + tooltip text provide the primary encoding.
 */
import * as topojson from "npm:topojson-client";
import * as d3 from "npm:d3";
import * as Plot from "npm:@observablehq/plot";

/**
 * @param {object} topo       - Pre-loaded TopoJSON object
 * @param {Array}  gapData    - Regional gap rows: { geography, absolute_gap, gap_direction, ethnicity }
 * @param {object} opts
 * @param {number}  opts.width
 * @param {string}  opts.title
 * @param {string}  opts.ethnicity  - Currently selected ethnicity label (for subtitle)
 */
export function choropleth(topo, gapData, {
  width = 420,
  title = "",
  ethnicity = "",
} = {}) {
  if (!topo) {
    const div = document.createElement("div");
    div.style = "padding:1rem; background:#f5f5f5; border-radius:6px; color:#666; font-size:0.9em; border:1px dashed #ccc;";
    div.textContent = "Map unavailable — TopoJSON not loaded.";
    return div;
  }
  const hasGapData = gapData?.length > 0;

  // Decode TopoJSON → GeoJSON feature collection
  const objectKey = Object.keys(topo.objects)[0];
  const geojson = topojson.feature(topo, topo.objects[objectKey]);

  // Build lookup: health_region name → worst (most adverse or largest) gap row
  const lookup = new Map();
  for (const row of gapData) {
    const existing = lookup.get(row.geography);
    if (!existing || Math.abs(row.absolute_gap) > Math.abs(existing.absolute_gap)) {
      lookup.set(row.geography, row);
    }
  }

  // Colour by gap direction + magnitude
  const adverseMax = d3.max(gapData ?? [], d => d.gap_direction === "adverse" ? Math.abs(d.absolute_gap) : 0) || 20;
  const colorScale = d3.scaleSequential()
    .domain([0, adverseMax])
    .interpolator(t => d3.interpolateReds(t * 0.85 + 0.1)); // avoid pure white at 0

  const fillColor = (feature) => {
    if (!hasGapData) return "#e0e0e0";
    const region = feature.properties?.health_region;
    const rec = lookup.get(region);
    if (!rec) return "#e0e0e0";
    if (rec.gap_direction === "adverse")   return colorScale(Math.abs(rec.absolute_gap));
    if (rec.gap_direction === "favourable") return "#4575b4";
    return "#ffffbf";
  };

  const tooltip = (feature) => {
    const dhb = feature.properties?.name ?? feature.properties?.DHB_name ?? "";
    const region = feature.properties?.health_region ?? "";
    const rec = lookup.get(region);
    if (!rec) return `${dhb}\n(${region})\nNo data`;
    const sign = rec.absolute_gap >= 0 ? "+" : "";
    return `${dhb}\n${region}\n${sign}${rec.absolute_gap?.toFixed(1)} pp (${rec.gap_direction})`;
  };

  return Plot.plot({
    width,
    height: Math.round(width * 1.55),
    projection: { type: "mercator", domain: geojson },
    title: title || `Regional equity gap${ethnicity ? ` — ${ethnicity}` : ""}`,
    subtitle: hasGapData
      ? "Each DHB coloured by its health region's equity gap. Red = adverse, blue = favourable."
      : "No regional breakdown available — NZHS provides national-level ethnicity data only.",
    style: { fontSize: "12px" },
    marks: [
      Plot.geo(geojson, {
        fill: fillColor,
        stroke: "white",
        strokeWidth: 0.8,
        title: tooltip,
      }),
      // Region name labels at centroids
      Plot.geo(geojson, Plot.centroid({
        text: d => {
          const region = d.properties?.health_region ?? "";
          // Abbreviate for legibility
          return region
            .replace("Northern | Te Tai Tokerau", "Northern\nTe Tai Tokerau")
            .replace("Midland | Te Manawa Taki", "Midland\nTe Manawa Taki")
            .replace("Central | Te Ikaroa", "Central\nTe Ikaroa")
            .replace("South Island | Te Waipounamu", "South Island\nTe Waipounamu");
        },
        fontSize: 9,
        fill: "#222",
        stroke: "white",
        strokeWidth: 3,
        paintOrder: "stroke",
        textAnchor: "middle",
      })),
    ],
  });
}
