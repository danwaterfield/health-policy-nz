export default {
  root: "src",
  base: "/health-policy-nz/",
  title: "NZ Health System Dashboard",
  style: "style.css",
  pages: [
    { name: "Overview", path: "/" },
    { name: "Indicator Explorer", path: "/explorer" },
    { name: "Equity", path: "/equity" },
    { name: "GPS Scorecard (2024–27)", path: "/scorecard" },
    { name: "Workforce", path: "/workforce" },
    { name: "Demand Forecast", path: "/forecast" },
    { name: "COVID Impact", path: "/trends" },
    { name: "Blind Spots", path: "/blind-spots" },
  ],
  footer: "Data sources: Ministry of Health NZ, Health New Zealand, Stats NZ, HQSC. " +
          "Open source. Not affiliated with the New Zealand Government.",
};
