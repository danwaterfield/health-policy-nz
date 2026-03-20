export default {
  root: "src",
  base: "/health-policy-nz/",
  title: "NZ Health System Dashboard",
  style: "style.css",
  head: `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' blob: https://*.basemaps.cartocdn.com; img-src 'self' data: blob: https://*.basemaps.cartocdn.com; style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'none';">
<meta name="description" content="A synthesis of public New Zealand health data — equity gaps, service access, workforce, and demand projections. Open source, zero cloud spend.">
<meta property="og:type" content="website">
<meta property="og:title" content="NZ Health System Dashboard">
<meta property="og:description" content="Equity gaps, service access, workforce pressure, and demand projections from NZ public health data. 19 indicators, 4 data sources, updated weekly.">
<meta property="og:image" content="https://danwaterfield.github.io/health-policy-nz/og-image.png">
<meta property="og:url" content="https://danwaterfield.github.io/health-policy-nz/">
<meta property="og:site_name" content="NZ Health System Dashboard">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="NZ Health System Dashboard">
<meta name="twitter:description" content="Equity gaps, service access, workforce pressure, and demand projections from NZ public health data.">
<meta name="twitter:image" content="https://danwaterfield.github.io/health-policy-nz/og-image.png">`,
  pages: [
    { name: "Overview", path: "/" },
    { name: "Indicator Explorer", path: "/explorer" },
    { name: "Equity", path: "/equity" },
    { name: "GPS Scorecard (2024–27)", path: "/scorecard" },
    { name: "Workforce", path: "/workforce" },
    { name: "Demand Forecast", path: "/forecast" },
    { name: "COVID Impact", path: "/trends" },
    { name: "Spatial Access", path: "/access" },
    { name: "Blind Spots", path: "/blind-spots" },
    { name: "Autoresearch", path: "/autoresearch" },
  ],
  footer: "Data sources: Ministry of Health NZ, Health New Zealand, Stats NZ, HQSC. " +
          "Open source. Not affiliated with the New Zealand Government.",
};
