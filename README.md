# NZ Health System Dashboard

A fully static dashboard synthesising public New Zealand health data — equity gaps, service access, workforce, and demand projections — built with zero cloud spend.

**Live site:** [danwaterfield.github.io/health-policy-nz](https://danwaterfield.github.io/health-policy-nz/)

## What It Shows

The dashboard brings together data from multiple NZ government sources to surface:

- **Equity gaps** — where Maori, Pacific, and other communities experience worse health outcomes than European/Other New Zealanders, with bias-adjusted estimates
- **Indicator explorer** — multi-year trends for 18 health indicators, filterable by ethnicity and region
- **GPS Scorecard** — accountability tracker for the Government Policy Statement on Health 2024-27
- **Workforce** — GP density, nurse vacancy rates, and regional shortfalls
- **Demand forecast** — projected health service need under low/medium/high demographic scenarios
- **COVID impact** — pre- vs post-pandemic trajectory shift analysis with structural break detection
- **Blind spots** — where the data simply does not exist to answer important questions

## Architecture

```
pipeline/               Python data pipeline
  fetch/                Download raw data from public sources
  transform/            Clean, normalise, load into DuckDB
  export.py             Export DuckDB tables to Parquet
  run_all.py            Orchestrator: fetch -> transform -> export
  config.py             All paths, URLs, and scorecard rules
  db.py                 DuckDB schema and connection management

src/                    Observable Framework static site
  *.md                  Dashboard pages (index, equity, scorecard, etc.)
  components/           Reusable JS chart components
  data/                 Parquet files consumed by the site

data/
  lookups/              CSV lookup tables (ethnicity, geography, indicators)
  raw/                  Downloaded source files (gitignored)
  dist/                 Exported Parquet files (gitignored)

tests/                  pytest test suite
```

### Pipeline stages

1. **Fetch** — each fetcher checks staleness before downloading, saves to `data/raw/`, and supports `dry_run=True`
2. **Transform** — each transformer reads raw files, resolves geography and ethnicity via DuckDB lookup tables (never hardcoded), and upserts into a dimensional model. Suppressed values (`'-'`, `'*'`, `'S'`, `'..'`) are coerced to NULL with `suppressed=TRUE`
3. **Export** — DuckDB tables are exported as Parquet to `data/dist/`, then copied into `src/data/` for the Observable build

### Database schema

Star schema in DuckDB:

| Layer | Tables |
|-------|--------|
| **Dimensions** | `dim_geography`, `dim_ethnicity`, `dim_time`, `dim_indicator`, `dim_data_source` |
| **Lookups** | `ethnicity_map`, `geography_map` (loaded from `data/lookups/`) |
| **Facts** | `fact_health_indicator`, `fact_service_access`, `fact_workforce`, `fact_life_tables`, `fact_nzdep`, `fact_electoral_roll`, `fact_corrections`, `fact_age_distribution`, `fact_policy_events` |
| **Derived** | `equity_gap`, `fact_demand_projection`, `fact_bias_estimates`, `blind_spots` |

### Site

Built with [Observable Framework](https://observablehq.com/framework/). Each page loads Parquet files via `DuckDBClient.of({})` and queries them with SQL — no server required. The site is deployed as static HTML/JS/CSS to GitHub Pages.

## Data sources

| Source | Type | Description |
|--------|------|-------------|
| **NZ Health Survey 2024-25** | Live download | Prevalence, rate ratios, and time series from the MoH Shiny app |
| **Stats NZ population projections** | Excel download | Subnational projections (low/medium/high scenarios) |
| **Stats NZ life tables 2017-19** | Excel download | Period life tables by ethnicity and sex (1,222 rows) |
| **NZDep2018** | Excel download | Deprivation index by SA1, aggregated to health regions (29,889 SA1s) |
| **Health NZ quarterly targets** | Seed CSV | ED wait times, elective surgery, cancer treatment, immunisation |
| **Workforce** | Seed CSV | GP and nurse density by district |
| **Electoral Commission** | Seed CSV | Maori roll enrolment statistics |
| **Corrections NZ** | Seed CSV | Prison population by ethnicity |
| **Census 2018 age distribution** | Seed CSV | Age structure by ethnicity |
| **PolicyTrace** | JSON bundle | NZ health policy timeline events (25 events, 1993-2025) |
| **DHB boundaries** | GeoJSON | District Health Board boundaries for choropleth maps |

## Getting started

### Prerequisites

- Python 3.12
- Node.js 20+
- npm

### Install dependencies

```bash
pip install -r requirements.txt
npm install
```

### Run the pipeline

```bash
# Full pipeline: fetch -> transform -> export
python -m pipeline.run_all

# Dry run (logs only, no downloads or DB writes)
python -m pipeline.run_all --dry-run

# Copy exported Parquet into the site data directory
make copy-data
```

### Local development

```bash
# Start the Observable Framework dev server
npm run dev
```

### Build the static site

```bash
# Full build: pipeline + copy data + Observable build
make build
```

### Run tests

```bash
python -m pytest tests/ -v
```

## Deployment

The site is deployed to GitHub Pages via a [GitHub Actions workflow](.github/workflows/build-and-deploy.yml) that runs weekly (Sunday 6pm UTC) or on manual dispatch. The workflow:

1. Runs the test suite
2. Executes the full data pipeline (with `PIPELINE_STALENESS_DAYS=0` to force fresh downloads)
3. Builds the static site with Observable Framework
4. Deploys to GitHub Pages

To trigger a manual deploy: **Actions** > **Refresh and Deploy** > **Run workflow**.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPELINE_STALENESS_DAYS` | `7` | Re-fetch if cached file older than this (CI sets to `0`) |
| `NZHS_CSV_URL` | MoH Shiny app URL | Override if upstream URL changes |
| `STATS_NZ_PROJECTIONS_URL` | Stats NZ URL | Override if upstream URL changes |
| `POLICYTRACE_LOCAL_PATH` | — | Path to local PolicyTrace bundle (skips HTTP fetch) |

Copy `.env.example` to `.env` if needed. Never commit `.env`.

## Equity gap methodology

The equity gap calculation (`pipeline/transform/equity_gap.py`) compares each indicator's value for Maori, Pacific, Asian, and other ethnic groups against the European/Other reference population at national level:

- Gaps are not computed against suppressed reference values
- Gaps are not computed when sample size < 30
- Gap direction (`adverse` / `favourable`) is determined by whether the indicator is `higher_better` or `lower_better`
- **Important caveat**: measured gaps are underestimates due to ethnic miscoding (~20% of Maori recorded as European/Other), NZHS survey exclusions (prisons, hospitals, residential care), and suppression of small cells

## Design conventions

- Confidence intervals shown as shaded bands when available
- Suppressed values rendered as grey hatched cells with explanatory tooltips
- Projections shown as dashed lines with italicised labels
- Equity gap colour scale: blue = favourable, red = adverse (with shape/pattern as secondary channel)
- Every chart includes source attribution and last-updated date
- All text meets WCAG AA contrast (4.5:1 minimum)
- Charts support CSV and PNG export

## License

This project uses publicly available New Zealand government data. Data is sourced from the Ministry of Health, Health New Zealand, Stats NZ, and other public agencies under their respective terms.
