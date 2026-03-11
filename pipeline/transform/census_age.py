"""
Census age distribution transformer.

Loads Stats NZ 2018 Census age distribution by ethnicity from seed CSV
into fact_age_distribution. Used for age-composition bias annotation
and as post-stratification weights for future MrP.
"""
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer


class CensusAgeTransformer(BaseTransformer):
    source_key = "census_age"

    def transform(self, path: Path, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would load census age distribution")
            return

        conn.execute("DELETE FROM fact_age_distribution")

        df = pd.read_csv(path)
        self.log(f"Loaded {len(df)} rows from {path}")

        eth_rows = conn.execute(
            "SELECT id, name FROM dim_ethnicity WHERE response_type = 'total_response'"
        ).fetchall()
        eth_map = {name: eid for eid, name in eth_rows}
        # Total maps to dim_ethnicity id=1 (the "Total" row)
        eth_map["Total"] = 1

        inserted = 0
        for _, row in df.iterrows():
            eth_name = str(row["ethnicity_name"]).strip()
            eth_id = eth_map.get(eth_name)

            conn.execute("""
                INSERT INTO fact_age_distribution
                    (id, ethnicity_id, age_band, age_from, age_to, pct, census_year, source)
                VALUES (nextval('fact_age_distribution_id_seq'), ?, ?, ?, ?, ?, ?, ?)
            """, (
                eth_id,
                str(row["age_band"]),
                int(row["age_from"]),
                int(row["age_to"]),
                float(row["pct"]),
                int(row["census_year"]),
                str(row["source"]),
            ))
            inserted += 1

        self.log(f"Done: {inserted} age distribution rows inserted")
