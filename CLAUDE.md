# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

A **static site proof of concept** for the NZ Health System Synthesis Dashboard. It ingests public NZ health datasets, stores them in DuckDB, exports Parquet files, and renders a fully static dashboard using Observable Framework — all with zero cloud spend.

**Constraint**: Do not introduce servers, cloud dependencies, databases requiring a running process, FastAPI/Flask, Docker, S3/Azure Blob, or any Node.js backend.

## Commands

```bash
# Python dependencies
pip install duckdb pandas requests beautifulsoup4 pyarrow pytest python-dotenv

# Observable Framework (JS)
npm install

# Run pipeline (fetch → transform → export Parquet)
make pipeline          # python pipeline/run_all.py

# Local site preview
make site              # cd src && npm run dev

# Full build (pipeline + static site)
make build

# Tests
pytest tests/ -v

# Single test file
pytest tests/test_equity_gap.py -v

# Dry run (logs only, no downloads or DB writes)
python pipeline/run_all.py --dry-run

# Clean all generated data
make clean
```

## Architecture

The pipeline runs in three stages:

1. **Fetch** (`pipeline/fetch/`): Each fetcher extends `BaseFetcher`, checks staleness before downloading, saves raw files to `data/raw/`, and returns the path. Accepts `dry_run=True`.

2. **Transform** (`pipeline/transform/`): Each transformer extends `BaseTransformer`, reads raw files, resolves geography/ethnicity via lookup tables in DuckDB (never hardcodes mappings), and upserts into DuckDB. Must be idempotent. Coerces `'-'`, `'*'`, `'S'`, `'..'`, `'...'` to NULL with `suppressed=TRUE`.

3. **Export** (`pipeline/export.py` / `pipeline/db.py`): DuckDB tables are exported as Parquet to `data/dist/`, which is then copied into `src/data/` for the Observable Framework build.

**Orchestrator**: `pipeline/run_all.py` runs all three stages in order.

**Config**: All paths and URLs live in `pipeline/config.py`. Never hardcode paths or URLs in fetch/transform scripts.

## Database Schema (DuckDB)

Dimensional model with:
- **Dimensions**: `dim_geography`, `dim_ethnicity`, `dim_time`, `dim_indicator`, `dim_data_source`
- **Lookup tables**: `ethnicity_map`, `geography_map` (loaded from `data/lookups/*.csv`)
- **Facts**: `fact_health_indicator`, `fact_service_access`, `fact_workforce`
- **Derived**: `equity_gap`, `fact_demand_projection`, `blind_spots`

Schema is created by `pipeline/db.py:init_schema()`. Connection via `get_conn()`.

## Equity Gap Calculation

`pipeline/transform/equity_gap.py` runs after all fact tables are populated. Reference population is European/Other at national level. Rules:
- Never compute a gap against a suppressed reference value
- Never compute a gap when sample_size < 30
- `gap_direction` is determined by `dim_indicator.direction` (`higher_better` / `lower_better`)

## Observable Framework Site (`src/`)

Pages: `index.md`, `equity.md`, `scorecard.md`, `workforce.md`, `forecast.md`, `blind-spots.md`

Data loading pattern — use `DuckDBClient.of({})` with `FileAttachment` for Parquet files, then query with SQL. See `AGENTS_POC.md` for the full pattern.

**Chart conventions**:
- Always render CI bands when `value_lower_ci`/`value_upper_ci` are non-null (`Plot.areaY` + `Plot.lineY`)
- Suppressed values: grey hatched cell or dashed outlined bar with explanatory tooltip
- Projections: dashed line + italicised label
- Equity gap colour: `interpolateRdYlBu` reversed (blue=favourable, red=adverse); never use colour as sole encoding — add shape/pattern as secondary channel
- Every chart footer: `Source: [name] | Last updated: [date] | [license]`
- All text must meet WCAG AA contrast (4.5:1 minimum)

## Testing

Fixtures in `tests/fixtures/` (~10 rows each, covering BOM, suppressed values, unknown geography/ethnicity codes).

- `test_fetch.py`: staleness check, BOM stripping
- `test_transform.py`: idempotency, suppression handling, unknown code handling, row count logging
- `test_equity_gap.py`: gap direction logic, suppression rules, sample size cutoff

## Environment Variables

```
PIPELINE_STALENESS_DAYS=7    # Re-fetch if cached file older than this (CI sets to 0)
NZHS_CSV_URL=<url>           # Overridable if upstream URLs change
STATS_NZ_PROJECTIONS_URL=<url>
```

Copy to `.env` — never commit.

## Key Data Source Notes

- **NZHS**: BOM present on some CSV exports — strip before parsing. Geography is health region only; do not impute finer granularity.
- **Health NZ Quarterly**: Uses legacy DHB codes — map via `geography_map` lookup.
- **Stats NZ Projections**: Three scenarios (low/medium/high) stored as `period_type='projection'` — these are the spine of the demand projection model.
- **Suppressed values** in source data (n < 30) must be respected: set `suppressed=TRUE`, do not impute.

## Production Handoff Notes

This PoC data layer carries forward to the production Django/Azure build:
- Fetchers → `ingestion/management/commands/ingest_*.py`
- Transformers → same commands using Django ORM
- DuckDB schema → Django models in `dimensions/` and `facts/` apps
- Observable Framework → Django templates + Chart.js + HTMX

The dimensional model, equity gap SQL, and projection logic are identical between environments.
