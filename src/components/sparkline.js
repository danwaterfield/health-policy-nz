/**
 * Trend sparkline with optional CI band.
 */
import * as Plot from "npm:@observablehq/plot";

export function sparkline(data, {
  x = "year",
  y = "value",
  yLower = "value_lower_ci",
  yUpper = "value_upper_ci",
  width = 120,
  height = 40,
  stroke = "#1f77b4",
} = {}) {
  const hasCi = data.some(d => d[yLower] != null && d[yUpper] != null);

  const marks = [];

  if (hasCi) {
    marks.push(
      Plot.areaY(data.filter(d => d[yLower] != null && d[yUpper] != null), {
        x,
        y1: yLower,
        y2: yUpper,
        fill: stroke,
        fillOpacity: 0.15,
      })
    );
  }

  marks.push(
    Plot.lineY(data, {
      x,
      y,
      stroke,
      strokeWidth: 1.5,
    })
  );

  return Plot.plot({
    width,
    height,
    axis: null,
    margin: 2,
    marks,
  });
}
