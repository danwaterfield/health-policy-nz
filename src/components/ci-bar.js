/**
 * Reusable bar chart with confidence interval bands.
 *
 * Usage:
 *   import { ciBar } from "./components/ci-bar.js";
 *   display(ciBar(data, { x: "region", y: "value", yLower: "value_lower_ci", yUpper: "value_upper_ci" }));
 */
import * as Plot from "npm:@observablehq/plot";

export function ciBar(data, {
  x,
  y,
  yLower = "value_lower_ci",
  yUpper = "value_upper_ci",
  fill = "#1f77b4",
  title,
  width = 700,
  marginLeft = 120,
  xLabel = "",
  yLabel = "",
  sourceNote = "",
} = {}) {
  const hasCi = data.some(d => d[yLower] != null && d[yUpper] != null);

  const marks = [
    Plot.ruleX([0]),
    Plot.barX(data, {
      x: y,
      y: x,
      fill,
      title: d => {
        const ci = hasCi && d[yLower] != null
          ? ` (95% CI: ${d[yLower]?.toFixed(1)}–${d[yUpper]?.toFixed(1)})`
          : "";
        return `${d[x]}: ${d[y]?.toFixed(1)}${ci}`;
      },
    }),
  ];

  if (hasCi) {
    marks.push(
      Plot.tickX(data.filter(d => d[yLower] != null), {
        x: yLower,
        y: x,
        stroke: "#333",
        strokeWidth: 1.5,
      }),
      Plot.tickX(data.filter(d => d[yUpper] != null), {
        x: yUpper,
        y: x,
        stroke: "#333",
        strokeWidth: 1.5,
      }),
      Plot.link(data.filter(d => d[yLower] != null && d[yUpper] != null), {
        x1: yLower,
        x2: yUpper,
        y1: x,
        y2: x,
        stroke: "#333",
        strokeWidth: 1.5,
      })
    );
  }

  const plot = Plot.plot({
    title,
    width,
    marginLeft,
    x: { label: xLabel },
    y: { label: yLabel },
    marks,
  });

  if (sourceNote) {
    const wrapper = document.createElement("div");
    wrapper.appendChild(plot);
    const footer = document.createElement("p");
    footer.style.cssText = "font-size: 0.8em; color: #666; margin-top: 0.25rem;";
    footer.textContent = sourceNote;
    wrapper.appendChild(footer);
    return wrapper;
  }

  return plot;
}

/**
 * Bar chart that shows suppressed values as hatched/dashed bars with tooltip.
 */
export function ciBarWithSuppression(data, opts = {}) {
  const { suppressed: suppressedKey = "suppressed", ...rest } = opts;
  const unsuppressed = data.filter(d => !d[suppressedKey]);
  const suppressed = data.filter(d => d[suppressedKey]);

  // Re-use ciBar for the non-suppressed portion and overlay suppressed markers
  // (Full hatching requires SVG pattern defs — simplified here as outlined bars)
  const marks = [];

  if (unsuppressed.length > 0) {
    marks.push(
      Plot.barX(unsuppressed, {
        x: rest.y,
        y: rest.x,
        fill: rest.fill ?? "#1f77b4",
      })
    );
  }

  if (suppressed.length > 0) {
    marks.push(
      Plot.barX(suppressed, {
        x: () => 0.5,  // placeholder width
        y: rest.x,
        fill: "none",
        stroke: "#999",
        strokeDasharray: "3,3",
        title: () => "Value suppressed: sample too small to report reliably. This area may have unmet need not visible in this data.",
      })
    );
  }

  return Plot.plot({
    title: rest.title,
    width: rest.width ?? 700,
    marginLeft: rest.marginLeft ?? 120,
    marks,
  });
}
