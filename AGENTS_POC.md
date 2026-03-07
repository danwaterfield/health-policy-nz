# AGENTS.md — NZ Health Dashboard (Static Site PoC)

> Context file for AI coding agents working on the proof-of-concept.
> Read this fully before writing any code. This is a zero-infrastructure local-first
> project. Do not introduce servers, cloud dependencies, or databases that require
> a running process.

---

## What This Is

A **static site proof of concept** for the NZ Health System Synthesis Dashboard described
in the full AGENTS.md. It validates the data pipeline, equity model, and visualisation
approach before committing to the production Django/Azure architecture.

Goals:
- Ingest real public NZ health datasets using Python scripts
- Store and query using DuckDB (in-process, no server)
- Export clean Parquet files consumed by the frontend
- Render a fully static, deployable dashboard using Observable Framework
- Run entirely on a local machine or GitHub Actions free tier
- Produce zero Azure spend

What carries forward to production: the dimensional model, equity gap calculation,
demand projection logic, and pipeline fetch/transform patterns. All of these become
Django management commands in the full build.

What does NOT carry forward: the static build process, Observable Framework, and
the DuckDB file itself. In production, DuckDB is replaced by PostgreSQL and
Observable is replaced by Django templates + Chart.js.

---

## Repository Layout

```
nz_health_poc/
├── pipeline/
│   ├── fetch/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseFetcher: cache check, download, save raw
│   │   ├── nzhs.py              # NZ Health Survey CSVs
│   │   ├── health_targets.py    # Health NZ quarterly wait time data
│   │   ├── demographics.py      # Stats NZ subnational population projections
│   │   ├── workforce.py         # Workforce density / vacancy publications
│   │   ├── pharmac.py           # PHARMAC dispensing summaries
│   │   └── hqsc.py              # HQSC quality indicator reports
│   ├── transform/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseTransformer: read raw → write DuckDB
│   │   ├── normalise.py         # Canonical ethnicity + geography mapping
│   │   ├── equity_gap.py        # Compute equity gap vs. reference population
│   │   ├── projections.py       # Age-specific utilisation × demographic forward model
│   │   └── blind_spots.py       # Data gap metadata → blind_spots table
│   ├── export.py                # DuckDB → Parquet export for each table
│   ├── db.py                    # DuckDB connection, schema creation, helpers
│   ├── config.py                # Paths, staleness thresholds, source URLs
│   └── run_all.py               # Orchestrator: fetch → transform → export
├── data/
│   ├── raw/                     # Downloaded source files — gitignored
│   ├── dist/                    # Parquet outputs consumed by Observable — gitignored
│   ├── lookups/                 # Static reference CSVs committed to repo
│   │   ├── ethnicity_map.csv    # Source label → canonical ethnicity
│   │   ├── geography_map.csv    # DHB legacy codes → health regions → Stats NZ codes
│   │   └── indicator_catalogue.csv
│   └── nz_health.duckdb         # Local DuckDB file — gitignored
├── src/                         # Observable Framework site
│   ├── .observablehq/
│   │   └── config.js
│   ├── index.md                 # Overview / homepage
│   ├── equity.md                # Equity gap choropleth + indicator explorer
│   ├── scorecard.md             # GPS 2024–27 accountability scorecard
│   ├── workforce.md             # Workforce pressure map + projections
│   ├── forecast.md              # Demand forecast explorer
│   ├── blind-spots.md           # Data gap panel
│   ├── components/
│   │   ├── choropleth.js        # Reusable D3 choropleth for NZ districts
│   │   ├── sparkline.js         # Trend sparkline with CI band
│   │   ├── scorecard-row.js     # GPS priority row with traffic light
│   │   ├── ci-bar.js            # Bar chart with error bars
│   │   └── suppressed-cell.js   # Suppressed value placeholder with tooltip
│   └── data/                    # Symlink or copy of data/dist/ at build time
├── tests/
│   ├── test_fetch.py
│   ├── test_transform.py
│   ├── test_equity_gap.py
│   └── fixtures/                # Minimal CSV fixtures per source
├── .github/
│   └── workflows/
│       └── build-and-deploy.yml
├── Makefile
├── requirements.txt
├── package.json                 # Observable Framework + D3 dependencies
└── AGENTS.md                    # This file
```

---

## Tech Stack

| Layer | Tool | Version | Notes |
|---|---|---|---|
| Data pipeline | Python | 3.12+ | Scripts only, no Django |
| Local datastore | DuckDB | 1.x | In-process, no server |
| Columnar export | Parquet | via DuckDB COPY | Consumed by Observable at build time |
| Static site | Observable Framework | latest | Markdown + JS + SQL |
| Client-side query | DuckDB-WASM | bundled by Observable | Same engine client + server |
| Charts | Observable Plot | bundled | D3-based; drop to raw D3 for complex visuals |
| Maps | D3 + TopoJSON | D3 v7 | NZ district boundaries as TopoJSON |
| CI/CD | GitHub Actions | — | Free tier, weekly schedule + manual dispatch |
| Hosting | GitHub Pages | — | Zero cost |

**Do not introduce:** FastAPI, Flask, any database requiring a running process,
any cloud storage (S3, Azure Blob), any authentication layer, any Node.js backend,
any Docker setup.

---

## Environment Setup

```bash
# Python dependencies
pip install duckdb pandas requests beautifulsoup4 pyarrow pytest python-dotenv

# Observable Framework
npm install

# Environment variables (copy to .env, never commit)
PIPELINE_STALENESS_DAYS=7        # Re-fetch if cached file older than this
NZHS_CSV_URL=<url>               # Overridable in case URLs change
STATS_NZ_PROJECTIONS_URL=<url>

# Run everything
make pipeline    # fetch + transform + export
make site        # npm run dev (local preview)
make build       # npm run build (production static)
make deploy      # push dist/ to gh-pages branch
```

---

## Makefile

```makefile
.PHONY: pipeline site build deploy test

pipeline:
	python pipeline/run_all.py

site:
	cd src && npm run dev

build:
	python pipeline/run_all.py
	cd src && npm run build

test:
	pytest tests/ -v

deploy: build
	cd src && npm run deploy

clean:
	rm -f data/nz_health.duckdb
	rm -rf data/dist/*
	rm -rf data/raw/*
```

---

## Pipeline

### `pipeline/config.py`

All paths and URLs live here. Never hardcode in fetch or transform scripts.

```python
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
RAW_DIR = ROOT / "data" / "raw"
DIST_DIR = ROOT / "data" / "dist"
LOOKUP_DIR = ROOT / "data" / "lookups"
DB_PATH = ROOT / "data" / "nz_health.duckdb"

STALENESS_DAYS = int(os.getenv("PIPELINE_STALENESS_DAYS", 7))

SOURCES = {
    "nzhs_prevalence": {
        "url": "https://minhealthnz.shinyapps.io/nz-health-survey-2024-25-annual-data-explorer/",
        "filename": "nzhs_prevalence.csv",
        "description": "NZ Health Survey prevalence/mean by subgroup",
    },
    # ... one entry per source file
}
```

### `pipeline/fetch/base.py`

```python
import hashlib
import time
from pathlib import Path
from pipeline.config import RAW_DIR, STALENESS_DAYS

class BaseFetcher:
    source_key: str  # must match SOURCES key in config

    def is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        age_days = (time.time() - path.stat().st_mtime) / 86400
        return age_days < STALENESS_DAYS

    def fetch(self, dry_run=False) -> Path:
        """Return path to raw file, downloading if necessary."""
        raise NotImplementedError

    def log(self, msg):
        print(f"[{self.__class__.__name__}] {msg}")
```

Every fetcher:
- Calls `self.is_fresh()` before downloading
- Saves to `RAW_DIR / filename` before any processing
- Returns the path to the saved file
- Accepts `dry_run=True` (logs what would happen, downloads nothing)
- Strips BOM on save if detected

### `pipeline/transform/base.py`

```python
import duckdb
from pipeline.db import get_conn

class BaseTransformer:
    source_key: str

    def transform(self, raw_path, conn: duckdb.DuckDBPyConnection, dry_run=False):
        """Read raw_path, write to DuckDB. Must be idempotent."""
        raise NotImplementedError

    def log(self, msg):
        print(f"[{self.__class__.__name__}] {msg}")
```

Every transformer:
- Uses `INSERT OR REPLACE` / upsert logic — idempotent on re-run
- Reads lookup tables from DuckDB (ethnicity_map, geography_map) — never hardcodes mappings in Python
- Coerces `'-'`, `'*'`, `'S'`, `'..'`, `'...'` to `NULL` and sets `suppressed = TRUE`
- Logs row counts: inserted, updated, suppressed, skipped

### `pipeline/db.py`

```python
import duckdb
from pipeline.config import DB_PATH

def get_conn() -> duckdb.DuckDBPyConnection:
    return duckdb.connect(str(DB_PATH))

def init_schema(conn):
    """Create all dimension and fact tables if they don't exist."""
    conn.execute(SCHEMA_SQL)

def export_parquet(conn, table: str, dest_dir):
    from pathlib import Path
    dest = Path(dest_dir) / f"{table}.parquet"
    conn.execute(f"COPY {table} TO '{dest}' (FORMAT PARQUET)")
    print(f"Exported {table} → {dest}")

SCHEMA_SQL = """
-- Dimensions
CREATE TABLE IF NOT EXISTS dim_geography (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    code VARCHAR,
    level VARCHAR CHECK (level IN ('national','health_region','district','area_unit')),
    rurality VARCHAR CHECK (rurality IN ('urban','rural','remote')),
    parent_id INTEGER REFERENCES dim_geography(id),
    dhb_legacy_code VARCHAR,
    stats_nz_code VARCHAR,
    centroid_lat DOUBLE,
    centroid_lon DOUBLE
);

CREATE TABLE IF NOT EXISTS dim_ethnicity (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    level1_code VARCHAR,
    level2_code VARCHAR,
    is_indigenous BOOLEAN DEFAULT FALSE,
    response_type VARCHAR CHECK (response_type IN ('total_response','prioritised'))
);

CREATE TABLE IF NOT EXISTS dim_time (
    id INTEGER PRIMARY KEY,
    year INTEGER,
    quarter INTEGER,
    period_label VARCHAR,
    period_type VARCHAR CHECK (period_type IN ('annual','quarterly','monthly','census','projection'))
);

CREATE TABLE IF NOT EXISTS dim_indicator (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    slug VARCHAR UNIQUE,
    category VARCHAR CHECK (category IN ('outcomes','access','workforce','determinants','quality')),
    direction VARCHAR CHECK (direction IN ('higher_better','lower_better')),
    unit VARCHAR,
    gps_priority VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_data_source (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    slug VARCHAR UNIQUE,
    url VARCHAR,
    publisher VARCHAR,
    cadence VARCHAR,
    methodology_notes TEXT,
    coverage_limitations TEXT,
    license VARCHAR,
    last_ingested_at TIMESTAMP
);

-- Lookup tables (loaded from data/lookups/ CSVs)
CREATE TABLE IF NOT EXISTS ethnicity_map (
    source_label VARCHAR PRIMARY KEY,
    canonical_ethnicity_id INTEGER REFERENCES dim_ethnicity(id)
);

CREATE TABLE IF NOT EXISTS geography_map (
    source_label VARCHAR,
    source_type VARCHAR,   -- 'dhb_name' | 'dhb_code' | 'health_region' | 'stats_code'
    canonical_geography_id INTEGER REFERENCES dim_geography(id),
    PRIMARY KEY (source_label, source_type)
);

-- Facts
CREATE TABLE IF NOT EXISTS fact_health_indicator (
    id INTEGER PRIMARY KEY,
    indicator_id INTEGER REFERENCES dim_indicator(id),
    geography_id INTEGER REFERENCES dim_geography(id),
    ethnicity_id INTEGER REFERENCES dim_ethnicity(id),
    time_id INTEGER REFERENCES dim_time(id),
    data_source_id INTEGER REFERENCES dim_data_source(id),
    value DOUBLE,
    value_lower_ci DOUBLE,
    value_upper_ci DOUBLE,
    sample_size INTEGER,
    suppressed BOOLEAN DEFAULT FALSE,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS fact_service_access (
    id INTEGER PRIMARY KEY,
    service_type VARCHAR CHECK (service_type IN ('ed','fsa','elective','primary','mental_health','aged_care')),
    geography_id INTEGER REFERENCES dim_geography(id),
    time_id INTEGER REFERENCES dim_time(id),
    data_source_id INTEGER REFERENCES dim_data_source(id),
    median_wait_days DOUBLE,
    pct_within_target DOUBLE,
    volume_seen INTEGER,
    volume_waiting INTEGER,
    volume_overdue INTEGER
);

CREATE TABLE IF NOT EXISTS fact_workforce (
    id INTEGER PRIMARY KEY,
    role_type VARCHAR CHECK (role_type IN ('gp','nurse','specialist','np','allied')),
    geography_id INTEGER REFERENCES dim_geography(id),
    time_id INTEGER REFERENCES dim_time(id),
    data_source_id INTEGER REFERENCES dim_data_source(id),
    fte_filled DOUBLE,
    fte_vacant DOUBLE,
    vacancy_rate DOUBLE,
    international_pct DOUBLE
);

-- Derived / computed tables
CREATE TABLE IF NOT EXISTS equity_gap (
    id INTEGER PRIMARY KEY,
    indicator_id INTEGER REFERENCES dim_indicator(id),
    geography_id INTEGER REFERENCES dim_geography(id),
    time_id INTEGER REFERENCES dim_time(id),
    reference_ethnicity_id INTEGER REFERENCES dim_ethnicity(id),
    target_ethnicity_id INTEGER REFERENCES dim_ethnicity(id),
    reference_value DOUBLE,
    target_value DOUBLE,
    absolute_gap DOUBLE,
    relative_gap DOUBLE,
    gap_direction VARCHAR CHECK (gap_direction IN ('adverse','neutral','favourable'))
);

CREATE TABLE IF NOT EXISTS fact_demand_projection (
    id INTEGER PRIMARY KEY,
    service_type VARCHAR,
    geography_id INTEGER REFERENCES dim_geography(id),
    time_id INTEGER REFERENCES dim_time(id),
    scenario VARCHAR CHECK (scenario IN ('baseline','high','low')),
    projected_volume DOUBLE,
    current_capacity DOUBLE,
    capacity_gap DOUBLE,
    projection_basis TEXT
);

-- Blind spots registry — populated by blind_spots.py transformer
CREATE TABLE IF NOT EXISTS blind_spots (
    id INTEGER PRIMARY KEY,
    domain VARCHAR,          -- 'mental_health' | 'disability' | 'pacific_subgroup' | etc.
    title VARCHAR,
    description TEXT,
    why_missing TEXT,
    best_proxy_indicator_id INTEGER REFERENCES dim_indicator(id),
    proxy_limitation TEXT,
    severity VARCHAR CHECK (severity IN ('high','medium','low')),
    further_reading_url VARCHAR
);
"""
```

### `pipeline/run_all.py`

```python
from pipeline.db import get_conn, init_schema, export_parquet
from pipeline.config import DIST_DIR
from pipeline.fetch.nzhs import NZHSFetcher
from pipeline.fetch.health_targets import HealthTargetsFetcher
from pipeline.fetch.demographics import DemographicsFetcher
from pipeline.fetch.workforce import WorkforceFetcher
from pipeline.transform.normalise import load_lookups
from pipeline.transform.nzhs import NZHSTransformer
from pipeline.transform.health_targets import HealthTargetsTransformer
from pipeline.transform.demographics import DemographicsTransformer
from pipeline.transform.equity_gap import EquityGapTransformer
from pipeline.transform.projections import ProjectionsTransformer
from pipeline.transform.blind_spots import BlindSpotsTransformer
import argparse

TABLES_TO_EXPORT = [
    "dim_geography", "dim_ethnicity", "dim_time",
    "dim_indicator", "dim_data_source",
    "fact_health_indicator", "fact_service_access",
    "fact_workforce", "equity_gap",
    "fact_demand_projection", "blind_spots",
]

def run(dry_run=False):
    conn = get_conn()
    init_schema(conn)
    load_lookups(conn)

    # Fetch
    fetchers = [NZHSFetcher(), HealthTargetsFetcher(), DemographicsFetcher(), WorkforceFetcher()]
    raw_paths = {f.source_key: f.fetch(dry_run=dry_run) for f in fetchers}

    # Transform
    NZHSTransformer().transform(raw_paths["nzhs_prevalence"], conn, dry_run)
    HealthTargetsTransformer().transform(raw_paths["health_targets"], conn, dry_run)
    DemographicsTransformer().transform(raw_paths["demographics"], conn, dry_run)
    WorkforceTransformer().transform(raw_paths["workforce"], conn, dry_run)

    # Derived
    EquityGapTransformer().transform(conn, dry_run)
    ProjectionsTransformer().transform(conn, dry_run)
    BlindSpotsTransformer().transform(conn, dry_run)

    # Export
    if not dry_run:
        DIST_DIR.mkdir(parents=True, exist_ok=True)
        for table in TABLES_TO_EXPORT:
            export_parquet(conn, table, DIST_DIR)

    conn.close()
    print("Pipeline complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
```

---

## Data Sources

### NZ Health Survey (`nzhs.py`)
- **URL**: Download CSV from the Annual Data Explorer
  (https://minhealthnz.shinyapps.io/nz-health-survey-2024-25-annual-data-explorer/)
- **License**: CC BY 4.0 — can be published in the static site
- **Files**: prevalence/mean file, subgroup comparisons file, time series file
- **Ethnicity**: total response — document in `dim_data_source.methodology_notes`
- **Geography**: health region only (no district). Do not impute finer granularity.
- **Suppression**: values based on n < 30 are suppressed in source — respect this, set `suppressed=TRUE`
- **Gotcha**: BOM present on some exports. Strip before parsing.

### Health NZ Quarterly Reports (`health_targets.py`)
- **URL**: https://www.tewhatuora.govt.nz — quarterly performance publications page
- **Format**: Excel or structured PDF; scrape the publications page for latest link
- **Covers**: ED 6-hour target, FSA wait times, elective treatment, cancer treatment, immunisation rates
- **Geography**: district level using legacy DHB codes — map via `geography_map` lookup

### Stats NZ Population Projections (`demographics.py`)
- **URL**: https://www.stats.govt.nz/information-releases/subnational-population-projections
- **Format**: Excel, multiple sheets (low/medium/high scenario, age × ethnicity × region)
- **Time**: 5-year bands to 2050 — store as `period_type='projection'` in `dim_time`
- **Note**: These are the spine of the demand projection model. Import all three scenarios.

### Workforce Data (`workforce.py`)
- **Primary**: Health NZ Workforce Plan PDFs, Medical Council of NZ annual reports
- **Secondary**: ASMS publications for vacancy context
- **GP density**: GP-per-population by district, published by Health NZ
- **Gap warning**: Nursing vacancy data is patchier than GP data — store what exists,
  populate `blind_spots` for the rest

### PHARMAC (`pharmac.py`)
- **URL**: https://www.pharmac.govt.nz/tools-resources/pharmaceutical-schedule/
- **Use**: Dispensing volume as proxy for chronic condition prevalence
- **Limitation**: measures prescribing, not diagnosis or outcomes — document this

### HQSC (`hqsc.py`)
- **URL**: https://www.hqsc.govt.nz/resources/
- **Use**: Adverse event counts, quality indicator summaries
- **Format**: Mixed PDF/Excel; parse summary tables only

---

## Equity Gap Calculation

File: `pipeline/transform/equity_gap.py`

This runs after all fact tables are populated. It computes gaps against the
reference population (European/Other, national level) for each indicator × geography × time.

```python
EQUITY_GAP_SQL = """
INSERT OR REPLACE INTO equity_gap
SELECT
    nextval('equity_gap_id_seq') as id,
    target.indicator_id,
    target.geography_id,
    target.time_id,
    ref.ethnicity_id                            AS reference_ethnicity_id,
    target.ethnicity_id                         AS target_ethnicity_id,
    ref.value                                   AS reference_value,
    target.value                                AS target_value,
    (target.value - ref.value)                  AS absolute_gap,
    ((target.value / NULLIF(ref.value, 0)) - 1) AS relative_gap,
    CASE
        WHEN ind.direction = 'higher_better' AND target.value < ref.value THEN 'adverse'
        WHEN ind.direction = 'lower_better'  AND target.value > ref.value THEN 'adverse'
        WHEN target.value = ref.value THEN 'neutral'
        ELSE 'favourable'
    END AS gap_direction
FROM fact_health_indicator target
JOIN fact_health_indicator ref
    ON  target.indicator_id  = ref.indicator_id
    AND target.time_id       = ref.time_id
    AND ref.geography_id     = (SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1)
    AND ref.ethnicity_id     = (SELECT id FROM dim_ethnicity WHERE name = 'European/Other' LIMIT 1)
JOIN dim_indicator ind ON target.indicator_id = ind.id
WHERE target.ethnicity_id IS NOT NULL
  AND target.suppressed = FALSE
  AND ref.suppressed = FALSE
  AND target.value IS NOT NULL
  AND ref.value IS NOT NULL;
"""
```

**Rules**:
- Never compute a gap against a suppressed reference value
- Never compute a gap when target sample_size < 30 — mark as suppressed in equity_gap too
- Log any indicator × geography × time combinations where the reference population
  value is missing (these are data gaps, surface them in the blind spots table)

---

## Demand Projection Model

File: `pipeline/transform/projections.py`

### Method
1. Calculate current **age-specific utilisation rates** per service type per geography:
   `rate = fact_service_access.volume_seen / dim_demographics.population_current`
2. Multiply by Stats NZ population projections for each age band × geography × scenario
3. Apply deferred demand multiplier where current `volume_overdue > 0`:
   `adjusted_volume = projected_volume × (1 + (volume_overdue / volume_seen) × 0.5)`
   (configurable in `config.py` as `DEFERRED_DEMAND_FACTOR`)
4. Compute `capacity_gap = projected_volume - current_capacity` (null if capacity unknown)
5. Store baseline, high, low scenarios

### Evidence-Based Leading Indicators to Include as Commentary Fields

These relationships are established in NZ literature. Model them as `projection_basis`
text notes on the relevant rows, not as quantitative adjustments (the PoC should not
overreach its evidence base):
- GP access difficulty → ED presentation rate (3-month lag)
- Housing deprivation quintile → child hospitalisation rate
- Workforce vacancy rate → median wait time growth
- Age 85+ population share → aged residential care demand
- Amenable mortality → GP density (long attribution window, rural)

---

## Observable Framework Site

### `src/.observablehq/config.js`

```js
export default {
  title: "NZ Health System Dashboard",
  pages: [
    { name: "Overview", path: "/" },
    { name: "Equity", path: "/equity" },
    { name: "GPS Scorecard", path: "/scorecard" },
    { name: "Workforce", path: "/workforce" },
    { name: "Demand Forecast", path: "/forecast" },
    { name: "Blind Spots", path: "/blind-spots" },
  ],
  footer: "Data sources: Ministry of Health NZ, Health New Zealand, Stats NZ, HQSC, PHARMAC. " +
          "Open source. Not affiliated with the New Zealand Government.",
};
```

### Data loading pattern in `.md` files

Observable Framework loads Parquet at build time via `FileAttachment`. Query with
DuckDB-WASM at build time for data that doesn't change per-user interaction, or
pass to client-side DuckDB for interactive filtering.

```js
// In any .md page
const db = await DuckDBClient.of({
  equity_gap: FileAttachment("data/equity_gap.parquet"),
  dim_geography: FileAttachment("data/dim_geography.parquet"),
  dim_indicator: FileAttachment("data/dim_indicator.parquet"),
  dim_ethnicity: FileAttachment("data/dim_ethnicity.parquet"),
});

// Example query
const moriGaps = await db.query(`
  SELECT
    g.name AS district,
    i.name AS indicator,
    eg.absolute_gap,
    eg.gap_direction
  FROM equity_gap eg
  JOIN dim_geography g ON eg.geography_id = g.id
  JOIN dim_indicator i ON eg.indicator_id = i.id
  JOIN dim_ethnicity e ON eg.target_ethnicity_id = e.id
  WHERE e.is_indigenous = TRUE
    AND eg.gap_direction = 'adverse'
  ORDER BY eg.absolute_gap DESC
`);
```

### Page: `src/equity.md`

Required elements:
- District-level choropleth coloured by equity gap magnitude for selected indicator
- Indicator selector (dropdown bound to `dim_indicator`)
- Ethnicity toggle: Māori / Pacific / All
- Time slider where multiple years available
- Below map: ranked table of districts by gap size with sparkline trend
- Suppressed cells must render as a hatched pattern with tooltip explaining suppression
- Data source footer on every chart: source name, last ingested date, license

### Page: `src/scorecard.md`

Five GPS 2024–27 priority rows (Access, Timeliness, Quality, Workforce, Value).
For each:
- Traffic light: green (on track) / amber (at risk) / red (off track)
- Trend arrow: improving / stable / worsening
- Current value vs. target
- Expand to see underlying indicators and their equity breakdown

Traffic light logic: defined as `gps_scorecard_rules` in `config.py`, not hardcoded
in the page. Rules specify the threshold values per indicator that define each status.

### Page: `src/blind-spots.md`

Cards rendered from the `blind_spots` table. Each card shows:
- Domain and title
- Why this data is missing
- Best available proxy (linked to indicator)
- Proxy limitation
- Severity indicator (high/medium/low — use colour + icon, not colour alone)
- Link to further reading

This page is as important as the quantitative pages. Make it prominent in the nav.

### Chart Conventions

**Uncertainty**: Always render CI bands where `value_lower_ci` and `value_upper_ci`
are non-null. Use `Plot.areaY` for band fill + `Plot.lineY` for the point estimate.
Never show a point estimate as a single pixel-precise line when CI data exists.

**Suppressed values**: Render as a grey hatched cell (choropleth) or a dashed
outlined bar (bar chart) with a tooltip: *"Value suppressed: sample too small
to report reliably. This area may have unmet need not visible in this data."*

**Estimated/modelled values**: Dashed line for projections; italicised label;
tooltip explaining the methodology in plain language.

**Colour palette**: Use a diverging scheme for equity gaps that is colour-blind safe.
Do not use red/green as the sole encoding. Use D3's `interpolateRdYlBu` reversed
(blue = favourable, red = adverse) with shape/pattern as a secondary channel.
All text must meet WCAG AA contrast (4.5:1 minimum).

**Attribution**: Every chart has a footer: `Source: [name] | Last updated: [date] | [license]`

---

## GitHub Actions

```yaml
# .github/workflows/build-and-deploy.yml
name: Refresh and Deploy

on:
  schedule:
    - cron: '0 6 * * 1'      # Weekly Monday 6am NZST ≈ Sunday 6pm UTC
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      contents: write         # needed for gh-pages push

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Python dependencies
        run: pip install -r requirements.txt

      - name: Run data pipeline
        run: python pipeline/run_all.py
        env:
          PIPELINE_STALENESS_DAYS: 0    # Always re-fetch in CI

      - uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Install Node dependencies
        run: npm ci

      - name: Copy Parquet to Observable data dir
        run: cp data/dist/*.parquet src/data/

      - name: Build static site
        run: npm run build

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./dist
```

Cache the `data/raw/` directory between runs using `actions/cache` keyed on
`hashFiles('pipeline/config.py')` to avoid re-downloading unchanged sources.

---

## Testing

Each test module uses minimal fixture CSVs in `tests/fixtures/` — one per source,
~10 rows, covering edge cases (BOM, suppressed values, unknown geography codes,
irregular headers).

### What each test must cover

**`test_fetch.py`**
- Fresh cache check: does not re-download if file is within staleness threshold
- BOM stripping: file with BOM saves cleanly and parses correctly

**`test_transform.py`**
- Idempotency: running transform twice produces same row count
- Suppression: `'*'`, `'S'`, `'-'`, `'..'` all become NULL with `suppressed=TRUE`
- Unknown geography: logs warning and skips row, does not create orphan geography
- Unknown ethnicity: same behaviour
- Row counts logged to stdout

**`test_equity_gap.py`**
- Gap direction correct for `higher_better` and `lower_better` indicators
- No gap computed when reference value is suppressed
- No gap computed when sample_size < 30
- Māori gap marked as `is_indigenous=TRUE` in resulting ethnicity join

Run with: `pytest tests/ -v`

---

## Known Data Gaps — Blind Spots to Register at Init

These rows should be seeded into the `blind_spots` table by `BlindSpotsTransformer`
on every run (upsert on `domain`):

| Domain | Severity | Why Missing |
|---|---|---|
| `mental_health_primary` | high | MH presentations in GP settings coded under other diagnoses; PHO data not public |
| `disability_under18` | high | 2023 Household Disability Survey excludes children from depth analysis |
| `pacific_subgroup` | high | Most national datasets aggregate all Pacific peoples; Samoan/Tongan/Cook Island granularity rare |
| `rural_gp_access_cost` | medium | GP density data exists; cost/travel-time access difficulty is survey-derived only, small-n at district level |
| `not_on_the_list` | high | People who never reach a GP/specialist never appear in waiting list data — modelled as unmet demand estimate only |
| `aged_care_quality` | medium | Residential care quality data fragmented; inspection reports not systematically structured |
| `maori_disability_intersect` | high | Māori + disabled intersection barely exists at district level in any public source |

---

## What This PoC Proves (and What It Doesn't)

### Proved by a working PoC
- Public NZ health CSVs are clean enough to ingest programmatically
- Geographic harmonisation (DHB codes → health regions → Stats NZ units) is tractable
- The equity gap calculation produces analytically sensible outputs
- Observable Framework's charting is expressive enough for CI bands and choropleths
- The demand projection method produces plausible forward estimates
- The "blind spots" framing is communicable to a non-technical audience
- The full pipeline runs in GitHub Actions free tier under 10 minutes

### Not proved / out of scope for PoC
- Multi-tenancy or per-client configuration
- PHO-level or practice-level data (not publicly available)
- Real-time or near-real-time data (not needed; this is a policy analysis tool)
- IDI-linked analysis (requires researcher accreditation; reference published IDI findings as static values only)
- Māori-community validation of equity framing (required before any public launch —
  treat PoC outputs as provisional pending that review)

---

## Handoff to Production (Django / Azure)

When the PoC is validated:

| PoC component | Production equivalent |
|---|---|
| `pipeline/fetch/*.py` | `ingestion/management/commands/ingest_*.py` |
| `pipeline/transform/*.py` | Same commands, using Django ORM instead of DuckDB |
| `pipeline/db.py` schema | Django models in `dimensions/` and `facts/` apps |
| DuckDB upsert logic | `Model.objects.update_or_create()` |
| `equity_gap` table | Materialised via management command or PostgreSQL materialised view |
| `blind_spots` table | Same structure as Django model |
| Observable Framework pages | Django views + Chart.js + HTMX |
| GitHub Actions runner | Azure App Service scheduled task or Azure Function |

The dimensional model, equity gap SQL, and projection logic are identical between
the two environments. The PoC is not a throwaway — it is the data layer.
