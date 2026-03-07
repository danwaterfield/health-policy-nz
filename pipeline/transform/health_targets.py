"""
Health Targets transformer.

Reads seed CSV and inserts into fact_service_access.
"""
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer
from pipeline.transform.normalise import coerce_suppressed

SERVICE_TYPE_MAP = {
    "ed": "ed",
    "emergency department": "ed",
    "fsa": "fsa",
    "first specialist assessment": "fsa",
    "elective": "elective",
    "cancer": "elective",
    "primary": "primary",
    "mental health": "mental_health",
    "aged care": "aged_care",
}


class HealthTargetsTransformer(BaseTransformer):
    source_key = "health_targets"

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

        # Ensure time entries
        time_map = {}
        for _, row in df.iterrows():
            year = row.get("year")
            quarter = row.get("quarter")
            try:
                year_int = int(float(str(year)))
                quarter_int = int(float(str(quarter))) if quarter and str(quarter) != "nan" else None
            except (ValueError, TypeError):
                continue
            key = (year_int, quarter_int)
            if key not in time_map:
                period_label = f"Q{quarter_int} {year_int}" if quarter_int else str(year_int)
                period_type = "quarterly" if quarter_int else "annual"
                conn.execute("""
                    INSERT INTO dim_time (id, year, quarter, period_label, period_type)
                    VALUES (nextval('dim_time_id_seq'), ?, ?, ?, ?)
                """, (year_int, quarter_int, period_label, period_type))
                result = conn.execute(
                    "SELECT id FROM dim_time WHERE year = ? AND quarter IS NOT DISTINCT FROM ? AND period_type = ?",
                    (year_int, quarter_int, period_type)
                ).fetchone()
                time_map[key] = result[0] if result else None

        data_source_id = 2  # Health Targets
        inserted = 0
        skipped = 0

        for _, row in df.iterrows():
            service_raw = str(row.get("service_type", "")).strip().lower()
            service_type = SERVICE_TYPE_MAP.get(service_raw)
            if not service_type:
                skipped += 1
                continue

            geography_label = str(row.get("district", row.get("region", "New Zealand"))).strip()
            geo_id = (
                geo_map.get((geography_label, "dhb_name"))
                or geo_map.get((geography_label, "dhb_code"))
                or geo_map.get((geography_label, "health_region"))
                or (1 if geography_label.lower() in ("new zealand", "total", "nz") else None)
            )
            if geo_id is None:
                self.log(f"WARNING: Unknown geography '{geography_label}' — skipping")
                skipped += 1
                continue

            year = row.get("year")
            quarter = row.get("quarter")
            try:
                year_int = int(float(str(year)))
                quarter_int = int(float(str(quarter))) if quarter and str(quarter) != "nan" else None
            except (ValueError, TypeError):
                skipped += 1
                continue
            time_id = time_map.get((year_int, quarter_int))

            def safe_float(val):
                v, _ = coerce_suppressed(str(val).strip())
                try:
                    return float(v) if v not in (None, "", "nan") else None
                except (ValueError, TypeError):
                    return None

            def safe_int(val):
                v, _ = coerce_suppressed(str(val).strip())
                try:
                    return int(float(v)) if v not in (None, "", "nan") else None
                except (ValueError, TypeError):
                    return None

            if not dry_run:
                conn.execute("""
                    INSERT INTO fact_service_access
                    (id, service_type, geography_id, time_id, data_source_id,
                     median_wait_days, pct_within_target, volume_seen, volume_waiting, volume_overdue)
                    VALUES (nextval('fact_service_access_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    service_type, geo_id, time_id, data_source_id,
                    safe_float(row.get("median_wait_days")),
                    safe_float(row.get("pct_within_target")),
                    safe_int(row.get("volume_seen")),
                    safe_int(row.get("volume_waiting")),
                    safe_int(row.get("volume_overdue")),
                ))
            inserted += 1

        self.log(f"Done: {inserted} rows inserted, {skipped} skipped")
