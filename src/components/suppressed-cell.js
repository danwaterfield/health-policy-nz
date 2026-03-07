/**
 * Suppressed value placeholder with tooltip.
 *
 * Renders a grey hatched cell for values suppressed due to small sample sizes.
 */
import { html } from "npm:htl";

/**
 * Render a suppressed value cell.
 * @param {string} reason - Optional reason text for the tooltip.
 */
export function suppressedCell(reason = "Value suppressed: sample too small to report reliably. This area may have unmet need not visible in this data.") {
  return html`
    <span
      title="${reason}"
      aria-label="Suppressed value"
      style="
        display: inline-block;
        width: 2.5em;
        height: 1.2em;
        background: repeating-linear-gradient(
          45deg,
          #ccc,
          #ccc 2px,
          #e8e8e8 2px,
          #e8e8e8 8px
        );
        border: 1px solid #aaa;
        border-radius: 2px;
        vertical-align: middle;
        cursor: help;
      "
    ></span>
  `;
}

/**
 * Format a value, showing suppressedCell if suppressed.
 */
export function formatOrSuppress(value, suppressed, formatter = d => d?.toFixed(1) ?? "—") {
  if (suppressed) return suppressedCell();
  if (value == null) return html`<span style="color: #999;">—</span>`;
  return formatter(value);
}
