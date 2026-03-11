"""Export all DuckDB tables to Parquet files in data/dist/."""
from pipeline.db import export_parquet
from pipeline.config import DIST_DIR

TABLES_TO_EXPORT = [
    "dim_geography",
    "dim_ethnicity",
    "dim_time",
    "dim_indicator",
    "dim_data_source",
    "fact_health_indicator",
    "fact_service_access",
    "fact_workforce",
    "equity_gap",
    "fact_demand_projection",
    "blind_spots",
    "fact_life_tables",
    "fact_nzdep",
    "fact_electoral_roll",
    "fact_corrections",
    "fact_age_distribution",
    "fact_bias_estimates",
    "fact_policy_events",
    # mrp_estimates omitted — stub table, empty until Stats NZ Data Lab access
]


def run(conn):
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    for table in TABLES_TO_EXPORT:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count == 0:
            print(f"WARNING: {table} has 0 rows — exporting empty Parquet")
        export_parquet(conn, table, DIST_DIR)
