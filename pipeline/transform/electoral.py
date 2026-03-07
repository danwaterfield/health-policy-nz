"""
Electoral Commission Māori roll transformer.

Loads the seed CSV and inserts into fact_electoral_roll.
National-level only (electorate boundaries don't align to health regions).
"""
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer


class ElectoralTransformer(BaseTransformer):
    source_key = "electoral"

    def transform(self, path: Path, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would load electoral roll data")
            return

        conn.execute("DELETE FROM fact_electoral_roll")

        df = pd.read_csv(path)
        self.log(f"Loaded {len(df)} rows from {path}")

        geo_rows = conn.execute(
            "SELECT id, name FROM dim_geography"
        ).fetchall()
        geo_map = {name: gid for gid, name in geo_rows}

        inserted = 0
        for _, row in df.iterrows():
            geo_name = str(row["geography_name"]).strip()
            geo_id = geo_map.get(geo_name) or geo_map.get("National") or geo_map.get("New Zealand")
            if geo_id is None:
                self.log(f"WARNING: no geography_id for '{geo_name}', skipping")
                continue

            conn.execute("""
                INSERT INTO fact_electoral_roll
                    (id, geography_id, year, eligible_maori_descent,
                     on_maori_roll, on_general_roll, maori_roll_pct, source)
                VALUES (nextval('fact_electoral_roll_id_seq'), ?, ?, ?, ?, ?, ?, ?)
            """, (
                geo_id,
                int(row["year"]),
                int(row["eligible_maori_descent"]),
                int(row["on_maori_roll"]),
                int(row["on_general_roll"]),
                float(row["maori_roll_pct"]),
                str(row["source"]),
            ))
            inserted += 1

        self.log(f"Done: {inserted} electoral roll rows inserted")
