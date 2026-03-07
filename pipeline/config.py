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

DEFERRED_DEMAND_FACTOR = 0.5

SOURCES = {
    "nzhs_prevalence": {
        "url": os.getenv(
            "NZHS_CSV_URL",
            "https://minhealthnz.shinyapps.io/nz-health-survey-2024-25-annual-data-explorer/",
        ),
        "filename": "nzhs_prevalence.csv",
        "description": "NZ Health Survey prevalence/mean by subgroup",
    },
    "health_targets": {
        "url": None,  # seed CSV — no download
        "filename": "health_targets_seed.csv",
        "description": "Health NZ quarterly health targets (seed data)",
    },
    "demographics": {
        "url": os.getenv(
            "STATS_NZ_PROJECTIONS_URL",
            "https://www.stats.govt.nz/information-releases/subnational-population-projections",
        ),
        "filename": "demographics.xlsx",
        "description": "Stats NZ subnational population projections",
    },
    "workforce": {
        "url": None,
        "filename": "workforce_seed.csv",
        "description": "Workforce density / vacancy seed data",
    },
    "nzdep": {
        "url": os.getenv(
            "NZDEP_URL",
            "https://www.otago.ac.nz/__data/assets/excel_doc/0026/332774/"
            "nzdep2018-statistical-area-1-sa1-with-higher-geographies-contains-"
            "sa1-sa2-territorial-authority-district-health-board-regional-council-823836.xlsx",
        ),
        "filename": "nzdep2018.xlsx",
        "description": "NZDep2018 index by SA1 with higher geographies (Otago University)",
    },
    "life_tables": {
        "url": os.getenv(
            "LIFE_TABLES_URL",
            "https://www.stats.govt.nz/assets/Uploads/National-and-subnational-period-life-tables/"
            "National-and-subnational-period-life-tables-2017-2019/Download-data/"
            "New-Zealand-period-life-tables-2017-2019.xlsx",
        ),
        "filename": "life_tables_2017_19.xlsx",
        "description": "Stats NZ national period life tables 2017-19 by ethnicity",
    },
    "electoral": {
        "url": None,  # seed CSV — Electoral Commission HTML page, not direct download
        "filename": "electoral_seed.csv",
        "description": "Electoral Commission Māori roll enrolment statistics 2023",
    },
    "corrections": {
        "url": None,  # seed CSV — Corrections NZ quarterly Excel requires JS
        "filename": "corrections_seed.csv",
        "description": "Corrections NZ prison population by ethnicity (Dec 2023)",
    },
    "boundaries": {
        "url": (
            "https://opendata.arcgis.com/api/v3/datasets/"
            "bab0ff4386eb4522b87d9cda6883f178_0/downloads/data"
            "?format=geojson&spatialRefId=4326"
        ),
        "filename": "nz-dhb.geojson",
        "description": "NZ DHB generalised boundaries (ArcGIS Open Data / eaglegis)",
    },
    "census_age": {
        "url": None,  # seed CSV — Stats NZ Census QuickStats aggregated manually
        "filename": "census_age_seed.csv",
        "description": "Stats NZ 2018 Census age distribution by ethnicity",
    },
}

# GPS 2024-27 scorecard rules: threshold values per indicator slug
# Format: {slug: {green: (min, max), amber: (min, max)}}  — red = outside amber
gps_scorecard_rules = {
    "ed_6hr_target": {
        "direction": "higher_better",
        "target": 95.0,
        "green_threshold": 90.0,   # >= green
        "amber_threshold": 80.0,   # >= amber, < green
    },
    "fsa_wait_days": {
        "direction": "lower_better",
        "target": 42.0,
        "green_threshold": 56.0,   # <= green (days)
        "amber_threshold": 84.0,   # <= amber, > green
    },
    "elective_treatment_pct": {
        "direction": "higher_better",
        "target": 100.0,
        "green_threshold": 95.0,
        "amber_threshold": 85.0,
    },
    "cancer_treatment_62day": {
        "direction": "higher_better",
        "target": 85.0,
        "green_threshold": 80.0,
        "amber_threshold": 70.0,
    },
    "childhood_immunisation": {
        "direction": "higher_better",
        "target": 95.0,
        "green_threshold": 90.0,
        "amber_threshold": 80.0,
    },
}
