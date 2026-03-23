---
title: Autoresearch — Counties Manukau

---

# Autoresearch: Counties Manukau

<p class="lead">Autonomous AI agents explored 887 healthcare configurations for Counties Manukau, modelling 50,000 residents interacting with 186 services over 52 weekly ticks.</p>

<p class="aside">All data is synthetic. Findings indicate what the <em>model</em> predicts, not what <em>will</em> happen. Validated across multiple seeds where noted.</p>

```js
import {exportButtons} from "./components/chart-export.js";
```

```js
const db = await DuckDBClient.of({
  agents: FileAttachment("data/sim_agents.parquet"),
  metrics: FileAttachment("data/sim_metrics.parquet"),
  timeline: FileAttachment("data/sim_timeline.parquet"),
  sensitivity: FileAttachment("data/sim_sensitivity.parquet"),
  causal: FileAttachment("data/sim_causal.parquet"),
});
```

```js
const agents = Array.from(await db.query(`SELECT * FROM agents ORDER BY accepted DESC`));
const timeline = Array.from(await db.query(`SELECT * FROM timeline`));
const metricsWide = Array.from(await db.query(`SELECT * FROM metrics`));
const causal = Array.from(await db.query(`SELECT * FROM causal`));
```

---

## Agent Fleet Performance

Seven agents explored different objectives simultaneously. Each proposes configuration changes, runs a simulation, and keeps improvements.

```js
const agentChart = Plot.plot({
  marginLeft: 140,
  marginRight: 60,
  height: 280,
  x: {label: "Experiments", grid: true},
  y: {label: null},
  color: {
    domain: ["Accepted", "Rejected"],
    range: ["#2a9d8f", "#e0e0e0"],
    legend: true,
  },
  marks: [
    Plot.barX(
      agents.flatMap(d => [
        {agent: d.agent, count: d.accepted, status: "Accepted"},
        {agent: d.agent, count: d.experiments - d.accepted, status: "Rejected"},
      ]),
      {
        y: "agent",
        x: "count",
        fill: "status",
        sort: {y: "-x"},
        tip: true,
      }
    ),
    Plot.text(agents, {
      y: "agent",
      x: d => d.experiments + 3,
      text: d => `${(d.acceptance_rate * 100).toFixed(0)}%`,
      textAnchor: "start",
      fontSize: 11,
      fill: "#666",
    }),
  ],
});
display(agentChart);
display(exportButtons(agentChart, agents, {filename: "agent-fleet"}));
```

---

## Headline Metrics: Baseline vs Best

How far did each agent move its primary metric from baseline?

```js
// Build comparison data
const comparison = agents.map(d => {
  const dir = d.direction;
  let baselineDist, bestDist, improvement;
  if (dir === "closer_to_1") {
    baselineDist = Math.abs(d.baseline_value - 1.0);
    bestDist = Math.abs(d.best_value - 1.0);
    improvement = baselineDist - bestDist;
  } else if (dir === "higher") {
    improvement = d.best_value - d.baseline_value;
  } else {
    improvement = d.baseline_value - d.best_value;
  }
  return {...d, improvement, improved: improvement > 0};
});
```

<div class="grid grid-cols-4">

```js
const eqAgent = comparison.find(d => d.agent_id === "equity_explorer");
display(html`<div class="card">
  <h3>Equity Gap</h3>
  <p style="font-size:2rem;font-weight:700;margin:0">${eqAgent.best_value.toFixed(3)}</p>
  <p class="muted">baseline ${eqAgent.baseline_value.toFixed(3)} &rarr; near parity</p>
</div>`);
```

```js
const maoAgent = comparison.find(d => d.agent_id === "maori_equity_explorer");
display(html`<div class="card">
  <h3>Maori Access Gap</h3>
  <p style="font-size:2rem;font-weight:700;margin:0">${maoAgent.best_value.toFixed(3)}</p>
  <p class="muted">baseline ${maoAgent.baseline_value.toFixed(3)} &rarr; +${(maoAgent.improvement * 100).toFixed(1)}pp</p>
</div>`);
```

```js
const rurAgent = comparison.find(d => d.agent_id === "rural_explorer");
display(html`<div class="card">
  <h3>Rural Access %</h3>
  <p style="font-size:2rem;font-weight:700;margin:0">${rurAgent.best_value.toFixed(1)}%</p>
  <p class="muted">baseline ${rurAgent.baseline_value.toFixed(1)}% &rarr; +${rurAgent.improvement.toFixed(1)}pp</p>
</div>`);
```

```js
const demAgent = comparison.find(d => d.agent_id === "demand_explorer");
display(html`<div class="card">
  <h3>Unmet Demand</h3>
  <p style="font-size:2rem;font-weight:700;margin:0">${demAgent.best_value.toFixed(1)}%</p>
  <p class="muted">baseline ${demAgent.baseline_value.toFixed(1)}% &rarr; &minus;${demAgent.improvement.toFixed(1)}pp</p>
</div>`);
```

</div>

---

## Improvement Trajectory

Each dot is an accepted experiment. Agents iteratively improve their primary metric.

```js
const selectedAgent = view(Inputs.select(
  new Map(agents.map(d => [d.agent, d.agent_id])),
  {label: "Agent", value: agents[0]?.agent_id}
));
```

```js
const agentTimeline = timeline.filter(d => d.agent_id === selectedAgent);
// Add sequential index
const indexed = agentTimeline.map((d, i) => ({...d, step: i + 1}));
const selectedPrimary = agents.find(d => d.agent_id === selectedAgent)?.primary_metric ?? "";
const baseVal = agents.find(d => d.agent_id === selectedAgent)?.baseline_value ?? 0;

const trajChart = Plot.plot({
  height: 300,
  x: {label: "Accepted experiment #"},
  y: {label: selectedPrimary, grid: true},
  marks: [
    Plot.ruleY([baseVal], {stroke: "#aaa", strokeDasharray: "4,3"}),
    Plot.text([{x: 0.5, y: baseVal}], {
      x: "x", y: "y", text: d => "baseline",
      dy: -8, fontSize: 10, fill: "#999",
    }),
    Plot.lineY(indexed, {x: "step", y: "primary_value", stroke: "#2a9d8f", strokeWidth: 2}),
    Plot.dot(indexed, {
      x: "step",
      y: "primary_value",
      fill: "#2a9d8f",
      r: 4,
      tip: true,
      title: d => `${d.experiment_id}\n${d.hypothesis?.slice(0, 80)}`,
    }),
  ],
});
display(trajChart);
display(exportButtons(trajChart, indexed, {filename: `trajectory-${selectedAgent}`}));
```

---

## Causal Links — Ranked by Evidence Strength

Which configuration changes reliably improve outcomes?

```js
const robustLinks = causal.filter(d => d.type === "robust");
const nonEffects = causal.filter(d => d.type === "non_effect");

const strengthColor = {strong: "#2a9d8f", moderate: "#e9c46a", weak: "#e76f51", none: "#ccc"};
const strengthValue = {strong: 4, moderate: 3, weak: 2, none: 1};

const causalRanked = causal
  .map(d => ({...d, label: `${d.change} → ${d.effect}`, numStrength: strengthValue[d.strength] ?? 0}))
  .sort((a, b) => b.numStrength - a.numStrength || a.label.localeCompare(b.label));

const causalChart = Plot.plot({
  marginLeft: 280,
  marginRight: 60,
  height: Math.max(200, causalRanked.length * 22),
  x: {label: "Evidence strength", domain: [0, 4], ticks: 4, tickFormat: d => ["", "none", "weak", "moderate", "strong"][d]},
  y: {label: null, domain: causalRanked.map(d => d.label)},
  subtitle: "Hover for evidence details",
  marks: [
    Plot.barX(causalRanked, {
      y: "label",
      x: "numStrength",
      fill: d => strengthColor[d.strength],
      tip: true,
      title: d => d.evidence,
    }),
    Plot.text(causalRanked, {
      y: "label",
      x: "numStrength",
      text: "strength",
      dx: 4,
      textAnchor: "start",
      fontSize: 10,
      fill: "#666",
    }),
  ],
});
display(causalChart);
```

<div class="grid grid-cols-2">

<div class="card">

**Robust findings**

${robustLinks.map(d => html`<p><strong style="color:${strengthColor[d.strength]}">${d.strength}</strong> &mdash; ${d.change} &rarr; ${d.effect}<br><span class="muted" style="font-size:0.85em">${d.evidence.slice(0, 120)}</span></p>`)}

</div>

<div class="card">

**Surprising non-effects**

${nonEffects.map(d => html`<p><strong style="color:#e76f51">no effect</strong> &mdash; ${d.change}<br><span class="muted" style="font-size:0.85em">${d.evidence.slice(0, 120)}</span></p>`)}

</div>

</div>

---

## Sensitivity Tests

Three policy interventions tested against baseline (3-seed average). All showed measurable improvement on their target metric.

```js
const sensMetrics = ["equity_gap", "maori_access_gap", "rural_access_pct", "unmet_demand_pct", "telehealth_utilisation"];
const sensData = Array.from(await db.query(`
  SELECT scenario, metric, value FROM sensitivity
  WHERE metric IN ('${sensMetrics.join("','")}')
`));

const pivoted = sensMetrics.flatMap(m =>
  ["Baseline", "Intervention A Extended Hours", "Intervention B Telehealth", "Intervention C Kaupapa Maori"].map(s => {
    const row = sensData.find(d => d.scenario === s && d.metric === m);
    return {metric: m, scenario: s.replace("Intervention ", "").replace("Baseline", "Baseline"), value: row?.value ?? 0};
  })
);

const sensChart = Plot.plot({
  height: 320,
  marginLeft: 160,
  marginBottom: 40,
  x: {label: null, tickRotate: -20},
  y: {label: null, grid: true},
  fx: {label: null},
  facet: {data: pivoted, x: "metric"},
  color: {
    domain: ["Baseline", "A Extended Hours", "B Telehealth", "C Kaupapa Maori"],
    range: ["#aaa", "#264653", "#2a9d8f", "#e9c46a"],
    legend: true,
  },
  marks: [
    Plot.barY(pivoted, {
      x: "scenario",
      y: "value",
      fill: "scenario",
      tip: true,
    }),
  ],
});
display(sensChart);
display(exportButtons(sensChart, pivoted, {filename: "sensitivity"}));
```

---

## Key Tensions

<div class="grid grid-cols-2">

<div class="card">

### Equity vs Maori Equity

The equity explorer achieves near-perfect deprivation parity (0.999) but its configuration scores **0.897** on Maori access. The Maori equity explorer achieves 0.945 on Maori access but only **0.978** on deprivation equity. These are partially misaligned goals requiring dual-target strategies.

</div>

<div class="card">

### Telehealth Convergence

Three independent agents (rural, Maori equity, demand) converged on telehealth expansion as their most effective lever. This is the strongest evidence in the fleet: **telehealth is a robust, multi-dimensional improvement** that simultaneously helps rural access, Maori equity, and unmet demand.

</div>

</div>

---

<p class="muted" style="font-size: 0.8em">
  Autoresearch simulation: Counties Manukau, 50K synthetic residents, 186 services, 887 experiments across 7 AI agents.
  All findings are model predictions on synthetic data.
</p>
