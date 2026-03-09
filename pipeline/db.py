import duckdb
from pipeline.config import DB_PATH, DIST_DIR
from pathlib import Path

SCHEMA_SQL = """
-- Sequences for ID generation
CREATE SEQUENCE IF NOT EXISTS dim_geography_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS dim_ethnicity_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS dim_time_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS dim_indicator_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS dim_data_source_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_health_indicator_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_service_access_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_workforce_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS equity_gap_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_demand_projection_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS blind_spots_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_life_tables_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_nzdep_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_electoral_roll_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_corrections_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_age_distribution_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS fact_bias_estimates_id_seq START 1;
CREATE SEQUENCE IF NOT EXISTS mrp_estimates_id_seq START 1;

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
    source_type VARCHAR,
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

-- Stats NZ period life tables by ethnicity group × age band × sex
CREATE TABLE IF NOT EXISTS fact_life_tables (
    id INTEGER PRIMARY KEY,
    ethnicity_group VARCHAR,       -- 'Maori', 'non-Maori', 'total'
    sex VARCHAR CHECK (sex IN ('total','male','female')),
    age_band VARCHAR,              -- '0', '1-4', '5-9', ..., '85+'
    age_from INTEGER,
    qx DOUBLE,                    -- probability of dying in this band
    lx DOUBLE,                    -- survivors per 100,000 to start of band
    ex DOUBLE,                    -- life expectancy at start of band
    year_range VARCHAR,            -- e.g. '2017-19'
    source VARCHAR
);

-- NZDep2018 index by health region (aggregated from SA1)
CREATE TABLE IF NOT EXISTS fact_nzdep (
    id INTEGER PRIMARY KEY,
    geography_id INTEGER REFERENCES dim_geography(id),
    year INTEGER,
    nzdep_mean_score DOUBLE,
    pct_q1 DOUBLE,   -- least deprived
    pct_q2 DOUBLE,
    pct_q3 DOUBLE,
    pct_q4 DOUBLE,
    pct_q5 DOUBLE,   -- most deprived
    sa1_count INTEGER,
    source VARCHAR
);

-- Electoral Commission Māori roll enrolment
CREATE TABLE IF NOT EXISTS fact_electoral_roll (
    id INTEGER PRIMARY KEY,
    geography_id INTEGER REFERENCES dim_geography(id),
    year INTEGER,
    eligible_maori_descent INTEGER,
    on_maori_roll INTEGER,
    on_general_roll INTEGER,
    maori_roll_pct DOUBLE,
    source VARCHAR
);

-- Corrections NZ prison population by ethnicity
CREATE TABLE IF NOT EXISTS fact_corrections (
    id INTEGER PRIMARY KEY,
    ethnicity_id INTEGER REFERENCES dim_ethnicity(id),
    year INTEGER,
    sentenced_count INTEGER,
    remand_count INTEGER,
    total_count INTEGER,
    pct_of_total DOUBLE,
    source VARCHAR
);

-- Census 2018 age distribution by ethnicity (for age composition bias annotation)
CREATE TABLE IF NOT EXISTS fact_age_distribution (
    id INTEGER PRIMARY KEY,
    ethnicity_id INTEGER REFERENCES dim_ethnicity(id),
    age_band VARCHAR,
    age_from INTEGER,
    age_to INTEGER,
    pct DOUBLE,
    census_year INTEGER,
    source VARCHAR
);

-- Bias estimates: quantified annotations on gap understatement by bias type
CREATE TABLE IF NOT EXISTS fact_bias_estimates (
    id INTEGER PRIMARY KEY,
    bias_type VARCHAR CHECK (bias_type IN (
        'ethnic_miscoding','survey_exclusion','age_composition',
        'total_response_dilution','small_cell_suppression'
    )),
    direction VARCHAR CHECK (direction IN ('understates_gap','overstates_gap','mixed')),
    magnitude_lower_pct DOUBLE,
    magnitude_upper_pct DOUBLE,
    applies_to VARCHAR,    -- 'all', or indicator slug, or ethnicity name
    notes TEXT,
    method VARCHAR,
    source VARCHAR,
    year INTEGER
);

-- MrP small-area estimates stub (populated when Stats NZ Data Lab access obtained)
CREATE TABLE IF NOT EXISTS mrp_estimates (
    id INTEGER PRIMARY KEY,
    indicator_id INTEGER REFERENCES dim_indicator(id),
    geography_id INTEGER REFERENCES dim_geography(id),
    ethnicity_id INTEGER REFERENCES dim_ethnicity(id),
    time_id INTEGER REFERENCES dim_time(id),
    estimate DOUBLE,
    lower_ci DOUBLE,
    upper_ci DOUBLE,
    n_effective DOUBLE,
    model_version VARCHAR,
    is_imputed BOOLEAN DEFAULT TRUE,
    source VARCHAR
);

-- PolicyTrace policy events (annotation overlay for charts)
CREATE TABLE IF NOT EXISTS fact_policy_events (
    id VARCHAR PRIMARY KEY,          -- legacy_id from PolicyTrace (e.g. nz-health-policy-0001)
    date DATE,
    date_precision VARCHAR,          -- day, month, year, unknown
    title TEXT,
    actor VARCHAR,
    category VARCHAR,                -- legislation, proposal, cabinet, etc.
    status VARCHAR,                  -- happened, proposed, reversed, contested
    tags VARCHAR,                    -- pipe-separated tag strings (e.g. turning_point)
    treaty_relevance VARCHAR,        -- yes, no, contested
    confidence_score DOUBLE,
    timeline_slug VARCHAR,
    source_url VARCHAR
);

-- Blind spots registry
CREATE TABLE IF NOT EXISTS blind_spots (
    id INTEGER PRIMARY KEY,
    domain VARCHAR UNIQUE,
    title VARCHAR,
    description TEXT,
    why_missing TEXT,
    best_proxy_indicator_id INTEGER REFERENCES dim_indicator(id),
    proxy_limitation TEXT,
    severity VARCHAR CHECK (severity IN ('high','medium','low')),
    further_reading_url VARCHAR
);
"""


def get_conn() -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH))


def init_schema(conn):
    """Create all dimension and fact tables if they don't exist."""
    conn.execute(SCHEMA_SQL)


def export_parquet(conn, table: str, dest_dir):
    dest = Path(dest_dir) / f"{table}.parquet"
    conn.execute(f"COPY {table} TO '{dest}' (FORMAT PARQUET)")
    print(f"Exported {table} -> {dest}")
