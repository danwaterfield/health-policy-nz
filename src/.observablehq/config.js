export default {
  root: "src",
  // Set base to match your GitHub repo name if deploying to GitHub Pages,
  // e.g. base: "/health-policy-nz/" — remove for custom domain
  title: "NZ Health System Dashboard",
  pages: [
    { name: "Overview", path: "/" },
    { name: "Equity", path: "/equity" },
    { name: "GPS Scorecard", path: "/scorecard" },
    { name: "Workforce", path: "/workforce" },
    { name: "Demand Forecast", path: "/forecast" },
    { name: "Pandemic Break", path: "/trends" },
    { name: "Blind Spots", path: "/blind-spots" },
  ],
  footer: "Data sources: Ministry of Health NZ, Health New Zealand, Stats NZ, HQSC. " +
          "Open source. Not affiliated with the New Zealand Government.",
};
