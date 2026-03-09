"""Workforce transformer — reads seed CSV into fact_workforce."""
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer
from pipeline.transform.normalise import coerce_suppressed

ROLE_TYPE_MAP = {
    "gp": "gp",
    "general practitioner": "gp",
    "nurse": "nurse",
    "registered nurse": "nurse",
    "specialist": "specialist",
    "nurse practitioner": "np",
    "np": "np",
    "allied": "allied",
    "allied health": "allied",
}


class WorkforceTransformer(BaseTransformer):
    source_key = "workforce"

    def transform(self, raw_path: Path, conn, dry_run=False):
        if not raw_path.exists():
            self.log(f"File not found: {raw_path} — skipping")
            return

        self.log(f"Reading {raw_path}")
        df = pd.read_csv(raw_path, encoding="utf-8-sig")
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        self.log(f"Read {len(df)} rows")

        geo_map = {
            (label, stype): gid
            for label, stype, gid in conn.execute(
                "SELECT source_label, source_type, canonical_geography_id FROM geography_map"
            ).fetchall()
        }

        conn.execute("DELETE FROM fact_workforce")

        data_source_id = 4  # Workforce
        inserted = 0
        skipped = 0

        for _, row in df.iterrows():
            role_raw = str(row.get("role_type", "")).strip().lower()
            role_type = ROLE_TYPE_MAP.get(role_raw)
            if not role_type:
                skipped += 1
                continue

            geography_label = str(row.get("district", row.get("region", "New Zealand"))).strip()
            geo_id = (
                geo_map.get((geography_label, "dhb_name"))
                or geo_map.get((geography_label, "health_region"))
                or (1 if geography_label.lower() in ("new zealand", "total", "nz") else None)
            )
            if geo_id is None:
                self.log(f"WARNING: Unknown geography '{geography_label}' — skipping")
                skipped += 1
                continue

            year = row.get("year")
            try:
                year_int = int(float(str(year)))
            except (ValueError, TypeError):
                skipped += 1
                continue

            result = conn.execute(
                "SELECT id FROM dim_time WHERE year = ? AND period_type = 'annual'",
                (year_int,)
            ).fetchone()
            if result:
                time_id = result[0]
            else:
                conn.execute("""
                    INSERT INTO dim_time (id, year, period_label, period_type)
                    VALUES (nextval('dim_time_id_seq'), ?, ?, 'annual')
                """, (year_int, str(year_int)))
                time_id = conn.execute(
                    "SELECT id FROM dim_time WHERE year = ? AND period_type = 'annual'",
                    (year_int,)
                ).fetchone()[0]

            def safe_float(col):
                v, _ = coerce_suppressed(str(row.get(col, "")).strip())
                try:
                    return float(v) if v not in (None, "", "nan") else None
                except (ValueError, TypeError):
                    return None

            if not dry_run:
                conn.execute("""
                    INSERT INTO fact_workforce
                    (id, role_type, geography_id, time_id, data_source_id,
                     fte_filled, fte_vacant, vacancy_rate, international_pct)
                    VALUES (nextval('fact_workforce_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    role_type, geo_id, time_id, data_source_id,
                    safe_float("fte_filled"),
                    safe_float("fte_vacant"),
                    safe_float("vacancy_rate"),
                    safe_float("international_pct"),
                ))
            inserted += 1

        self.log(f"Done: {inserted} rows inserted, {skipped} skipped")
