# NZ Health System Synthesis Dashboard

A static dashboard synthesising public New Zealand health datasets to surface equity gaps, workforce pressures, and demand projections. Built with DuckDB, Python, and [Observable Framework](https://observablehq.com/framework/). Zero cloud spend — runs entirely locally and deploys to GitHub Pages.

**Live site**: https://danwaterfield.github.io/health-policy-nz/

---

## What it shows

| Page | Content |
|------|---------|
| **Overview** | Summary cards — indicator count, adverse equity gaps, data freshness |
| **Equity Gap Explorer** | Māori and Pacific health gaps vs European/Other, by indicator, region, and year. Includes CI bands, suppression handling, NZDep deprivation context, life expectancy, and bias estimates |
| **GPS Scorecard** | Traffic-light scorecard tracking the five Government Policy Statement 2024–27 health targets |
| **Workforce** | GP and nursing vacancy rates by district; international recruitment dependency |
| **Demand Forecast** | Population-adjusted service demand projections (baseline/high/low) from Stats NZ subnational projections |
| **Pandemic Break** | Pre/post COVID slope comparison — which equity gaps worsened or improved in trajectory |
| **Blind Spots** | Seven structural data absences that constrain equity analysis |

---

## Architecture

```
data/raw/          ← fetched source files (gitignored)
data/lookups/      ← manually maintained seed CSVs
data/dist/         ← exported Parquet files (gitignored)
pipeline/
  config.py        ← all paths, URLs, GPS scorecard rules
  db.py            ← DuckDB schema + export
  fetch/           ← one fetcher per source, all extend BaseFetcher
  transform/       ← one transformer per source, all extend BaseTransformer
  export.py        ← exports all tables to Parquet
  run_all.py       ← orchestrator
src/               ← Observable Framework site
  *.md             ← dashboard pages
  components/      ← reusable JS chart components
  data/            ← Parquet files served to the browser (gitignored)
```

**Pipeline stages**: Fetch → Transform → Derived (equity gaps, projections, bias estimates) → Export Parquet → Observable build reads Parquet via DuckDB-WASM in the browser.

---

## Data sources

| Source | Method | Notes |
|--------|--------|-------|
| NZ Health Survey 2024/25 | HTTP download | Direct static CSV from Shiny app |
| Health NZ quarterly targets | Seed CSV | PDF source — manually extracted |
| Stats NZ population projections | Seed CSV | Falls back from Excel download |
| NZDep2018 | Excel download | 29,889 SA1 rows, Otago University |
| Stats NZ life tables 2017–19 | Excel download | 1,222 rows, 6 ethnicity × 2 sex groups |
| Electoral Commission Māori roll | Seed CSV | 2023 national figures |
| Corrections NZ prison population | Seed CSV | Dec 2023, by ethnicity |
| DHB boundaries | GeoJSON download | ArcGIS Open Data |
| PolicyTrace nz-health-policy | JSON download | 25 policy events 1993–2025, i4i bundle |

---

## Quickstart

```bash
# Python dependencies
pip install -r requirements.txt

# Node dependencies
npm install

# Run the data pipeline
python3 -m pipeline.run_all

# Copy Parquet files to Observable's data directory
cp data/dist/*.parquet src/data/

# Start local dev server
npm run dev

# Full static build
npm run build
```

For a dry run (logs only, no downloads or DB writes):

```bash
python3 -m pipeline.run_all --dry-run
```

---

## Environment variables

Copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `PIPELINE_STALENESS_DAYS` | `7` | Re-fetch cached files older than this many days |
| `NZHS_CSV_URL` | NZHS Shiny app URL | Override if upstream URL changes |
| `STATS_NZ_PROJECTIONS_URL` | Stats NZ URL | Override if upstream URL changes |
| `POLICYTRACE_LOCAL_PATH` | *(unset)* | Path to local PolicyTrace `site/data/` directory for dev |
| `POLICYTRACE_BUNDLE_URL` | GitHub Pages URL | Override PolicyTrace bundle source |

---

## Tests

```bash
pytest tests/ -v
```

Fixtures in `tests/fixtures/` cover BOM handling, suppression markers, idempotency, unknown geography/ethnicity codes, and equity gap direction logic.

---

## CI/CD

A GitHub Actions workflow (`.github/workflows/build-and-deploy.yml`) runs weekly (Sunday 6am NZST) and on manual dispatch. It:

1. Fetches fresh data (`PIPELINE_STALENESS_DAYS=0`)
2. Runs the pipeline
3. Builds the Observable Framework static site
4. Deploys to GitHub Pages

---

## Key design decisions

**Why DuckDB + Parquet?** The entire analytical layer runs in the browser via DuckDB-WASM. No server, no API, no cloud spend. The pipeline produces Parquet files that Observable Framework serves as static assets.

**Why seed CSVs for some sources?** Several Health NZ sources are image-based PDFs or JS-rendered pages with no direct download path. Seed CSVs committed to `data/lookups/` are the pragmatic alternative — update them manually when new quarterly data is published.

**Equity gaps are floor estimates.** Every known data bias (ethnic miscoding, survey exclusions, suppression of small cells, no age standardisation) runs in the direction of understating Māori/Pacific disadvantage. The gaps shown are conservative lower bounds.

**PolicyTrace integration.** Policy events from the [PolicyTrace](https://github.com/danwaterfield/policytrace) nz-health-policy timeline are fetched at pipeline time and stored in `fact_policy_events`. Turning-point events appear as annotation overlays on time series charts. Set `POLICYTRACE_LOCAL_PATH` to your local PolicyTrace checkout during development.

---

## Licence

Data sources retain their original licences (Stats NZ and Ministry of Health data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)). Dashboard code: MIT.
