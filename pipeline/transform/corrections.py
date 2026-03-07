"""
Corrections NZ prison population transformer.

Loads seed CSV and inserts into fact_corrections. Used to estimate the
survey exclusion bias — NZHS does not survey the prison population, which
is disproportionately Māori and Pacific with worse health outcomes.
"""
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer


class CorrectionsTransformer(BaseTransformer):
    source_key = "corrections"

    def transform(self, path: Path, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would load Corrections NZ data")
            return

        conn.execute("DELETE FROM fact_corrections")

        df = pd.read_csv(path)
        self.log(f"Loaded {len(df)} rows from {path}")

        # Build ethnicity lookup (total_response)
        eth_rows = conn.execute(
            "SELECT id, name FROM dim_ethnicity WHERE response_type = 'total_response'"
        ).fetchall()
        eth_map = {name: eid for eid, name in eth_rows}

        inserted = 0
        for _, row in df.iterrows():
            eth_name = str(row["ethnicity_name"]).strip()
            eth_id = eth_map.get(eth_name)
            # Try partial match for European/Other variations
            if eth_id is None:
                for k, v in eth_map.items():
                    if eth_name.lower() in k.lower() or k.lower() in eth_name.lower():
                        eth_id = v
                        break

            conn.execute("""
                INSERT INTO fact_corrections
                    (id, ethnicity_id, year, sentenced_count, remand_count,
                     total_count, pct_of_total, source)
                VALUES (nextval('fact_corrections_id_seq'), ?, ?, ?, ?, ?, ?, ?)
            """, (
                eth_id,  # may be None for unlisted ethnicities
                int(row["year"]),
                int(row["sentenced_count"]),
                int(row["remand_count"]),
                int(row["total_count"]),
                float(row["pct_of_total"]),
                str(row["source"]),
            ))
            inserted += 1

        self.log(f"Done: {inserted} corrections rows inserted")
