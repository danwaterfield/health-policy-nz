/**
 * Data freshness bar showing age of each data source.
 *
 * Usage:
 *   import {dataFreshness} from "./components/data-freshness.js";
 *   display(dataFreshness(sourceFreshness));
 */
export function dataFreshness(sources) {
  if (!sources || sources.length === 0) return document.createElement("div");

  const container = document.createElement("div");
  container.style.cssText = "padding: 0.75rem 1rem; background: #f8f8f8; border-radius: 6px; font-size: 0.82em; border: 1px solid #eee;";

  const label = document.createElement("strong");
  label.textContent = "Data freshness: ";
  container.appendChild(label);

  sources.forEach((s, i) => {
    const age = s.last_ingested_at
      ? Math.floor((Date.now() - new Date(s.last_ingested_at).getTime()) / 86400000)
      : null;
    const color = age === null ? "#636363" : age < 14 ? "#2d8a4e" : age < 90 ? "#e5850b" : "#c0392b";
    const ageLabel = age === null ? "not yet ingested" : age === 0 ? "today" : `${age}d ago`;

    const span = document.createElement("span");
    span.style.cssText = "margin-right: 1.5rem; white-space: nowrap;";

    const ageSpan = document.createElement("span");
    ageSpan.style.cssText = `color: ${color}; font-weight: 600;`;
    ageSpan.textContent = ageLabel;

    span.appendChild(ageSpan);
    span.appendChild(document.createTextNode(" " + s.name));
    container.appendChild(span);
  });

  return container;
}
