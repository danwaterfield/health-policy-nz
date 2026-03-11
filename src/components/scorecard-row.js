/**
 * GPS scorecard row component: traffic light + trend arrow.
 */
import { html } from "npm:htl";

/**
 * Render a traffic light indicator.
 * @param {string} status - "green" | "amber" | "red" | "unknown"
 */
export function trafficLight(status) {
  const config = {
    green: { color: "#2d8a4e", label: "On track", symbol: "●" },
    amber: { color: "#e5850b", label: "At risk", symbol: "●" },
    red: { color: "#c0392b", label: "Off track", symbol: "●" },
    unknown: { color: "#636363", label: "No data", symbol: "●" },
  };
  const c = config[status] ?? config.unknown;
  return html`<span
    style="color: ${c.color}; font-size: 1.4em;"
    title="${c.label}"
    aria-label="${c.label}"
  >${c.symbol}</span>`;
}

/**
 * Render a trend arrow.
 * @param {number|null} delta - positive = improving (based on direction), negative = worsening
 * @param {string} direction - "higher_better" | "lower_better"
 */
export function trendArrow(delta, direction) {
  if (delta == null || isNaN(delta)) {
    return html`<span style="color: #636363;" aria-label="No trend data">→</span>`;
  }

  const improving = direction === "higher_better" ? delta > 0 : delta < 0;
  const stable = Math.abs(delta) < 0.5;

  if (stable) {
    return html`<span style="color: #636363;" aria-label="Stable">→</span>`;
  }
  if (improving) {
    return html`<span style="color: #2d8a4e;" aria-label="Improving">↑</span>`;
  }
  return html`<span style="color: #c0392b;" aria-label="Worsening">↓</span>`;
}

/**
 * Compute traffic light status from a value and threshold.
 */
export function computeStatus(value, threshold, direction) {
  if (value == null || threshold == null) return "unknown";
  if (direction === "higher_better") {
    if (value >= threshold) return "green";
    if (value >= threshold * 0.85) return "amber";
    return "red";
  } else {
    if (value <= threshold) return "green";
    if (value <= threshold * 1.15) return "amber";
    return "red";
  }
}
