/**
 * CSV and PNG export buttons for charts and data tables.
 *
 * Usage:
 *   import { exportButtons } from "./components/chart-export.js";
 *   display(exportButtons(plotElement, data, { filename: "equity-gap" }));
 */

/**
 * Serialize an array of objects to CSV string.
 */
function toCsv(data) {
  if (!data || data.length === 0) return "";
  const cols = Object.keys(data[0]);
  const header = cols.map(c => `"${c}"`).join(",");
  const rows = data.map(row =>
    cols.map(c => {
      const v = row[c];
      if (v == null) return "";
      if (typeof v === "string") return `"${v.replace(/"/g, '""')}"`;
      return String(v);
    }).join(",")
  );
  return [header, ...rows].join("\n");
}

/**
 * Trigger a browser download of a string as a file.
 */
function downloadBlob(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/**
 * Convert an SVG element to a PNG data URL via canvas.
 */
async function svgToPng(svgElement, scale = 2) {
  const svgData = new XMLSerializer().serializeToString(svgElement);
  const svgBlob = new Blob([svgData], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(svgBlob);

  const img = new Image();
  img.crossOrigin = "anonymous";

  return new Promise((resolve, reject) => {
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width * scale;
      canvas.height = img.height * scale;
      const ctx = canvas.getContext("2d");
      ctx.scale(scale, scale);
      ctx.fillStyle = "white";
      ctx.fillRect(0, 0, img.width, img.height);
      ctx.drawImage(img, 0, 0);
      URL.revokeObjectURL(url);
      canvas.toBlob(blob => resolve(blob), "image/png");
    };
    img.onerror = reject;
    img.src = url;
  });
}

/**
 * Create export buttons (CSV + PNG) for a chart and its data.
 *
 * @param {HTMLElement|null} plotElement - The rendered Plot SVG element (for PNG export). Pass null to skip PNG.
 * @param {Array} data - Array of row objects for CSV export.
 * @param {Object} opts
 * @param {string} opts.filename - Base filename without extension.
 */
export function exportButtons(plotElement, data, { filename = "chart-data" } = {}) {
  const container = document.createElement("div");
  container.style.cssText = "display: flex; gap: 0.5rem; margin: 0.5rem 0; align-items: center;";

  // CSV button
  if (data && data.length > 0) {
    const csvBtn = document.createElement("button");
    csvBtn.textContent = "CSV";
    csvBtn.title = "Download data as CSV";
    csvBtn.style.cssText = "font-size: 0.75em; padding: 3px 10px; border: 1px solid #aaa; border-radius: 4px; background: #f8f8f8; cursor: pointer; color: #333;";
    csvBtn.addEventListener("click", () => {
      downloadBlob(toCsv(data), `${filename}.csv`, "text/csv");
    });
    container.appendChild(csvBtn);
  }

  // PNG button
  if (plotElement) {
    const pngBtn = document.createElement("button");
    pngBtn.textContent = "PNG";
    pngBtn.title = "Download chart as PNG";
    pngBtn.style.cssText = "font-size: 0.75em; padding: 3px 10px; border: 1px solid #aaa; border-radius: 4px; background: #f8f8f8; cursor: pointer; color: #333;";
    pngBtn.addEventListener("click", async () => {
      const svg = plotElement.querySelector("svg") ?? plotElement;
      if (svg.tagName !== "svg") return;
      const blob = await svgToPng(svg);
      if (blob) {
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${filename}.png`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }
    });
    container.appendChild(pngBtn);
  }

  return container;
}
