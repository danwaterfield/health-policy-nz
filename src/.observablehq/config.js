export default {
  root: "src",
  base: "/health-policy-nz/",
  title: "NZ Health System Dashboard",
  style: "style.css",
  head: `<meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; connect-src 'self' blob:; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; object-src 'none'; base-uri 'self'; form-action 'none';">`,
  pages: [
    { name: "Overview", path: "/" },
    { name: "Indicator Explorer", path: "/explorer" },
    { name: "Equity", path: "/equity" },
    { name: "GPS Scorecard (2024–27)", path: "/scorecard" },
    { name: "Workforce", path: "/workforce" },
    { name: "Demand Forecast", path: "/forecast" },
    { name: "COVID Impact", path: "/trends" },
    { name: "Blind Spots", path: "/blind-spots" },
    { name: "Autoresearch", path: "/autoresearch" },
  ],
  footer: "Data sources: Ministry of Health NZ, Health New Zealand, Stats NZ, HQSC. " +
          "Open source. Not affiliated with the New Zealand Government.",
};
