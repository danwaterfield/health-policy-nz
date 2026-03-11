"""
Stats NZ subnational population projections transformer.

Handles both Excel (automated download) and seed CSV (fallback).
Populates dim_time with projection periods and seeds fact_demand_projection basis data.
"""
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer


SCENARIO_SHEET_MAP = {
    "low": ["low", "low growth", "scenario 1"],
    "medium": ["medium", "medium growth", "scenario 2", "central"],
    "high": ["high", "high growth", "scenario 3"],
}


class DemographicsTransformer(BaseTransformer):
    source_key = "demographics"

    def transform(self, raw_path: Path, conn, dry_run=False):
        if not raw_path.exists():
            self.log(f"File not found: {raw_path} — skipping")
            return

        suffix = raw_path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            self._transform_excel(raw_path, conn, dry_run)
        elif suffix == ".csv":
            self._transform_csv(raw_path, conn, dry_run)
        else:
            self.log(f"Unknown file type: {suffix} — skipping")

    def _transform_csv(self, raw_path: Path, conn, dry_run=False):
        """Handle seed CSV fallback."""
        self.log(f"Reading CSV {raw_path}")
        df = pd.read_csv(raw_path, encoding="utf-8-sig")
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
        self.log(f"Read {len(df)} rows from seed CSV")
        self._insert_projections(df, conn, dry_run)

    def _transform_excel(self, raw_path: Path, conn, dry_run=False):
        """Handle Stats NZ Excel workbook."""
        self.log(f"Reading Excel {raw_path}")
        try:
            xl = pd.ExcelFile(raw_path)
        except Exception as e:
            self.log(f"Failed to open Excel: {e}")
            return

        self.log(f"Sheets: {xl.sheet_names}")

        geo_map = {
            (label, stype): gid
            for label, stype, gid in conn.execute(
                "SELECT source_label, source_type, canonical_geography_id FROM geography_map"
            ).fetchall()
        }

        inserted = 0
        for scenario, sheet_keywords in SCENARIO_SHEET_MAP.items():
            sheet = self._find_sheet(xl.sheet_names, sheet_keywords)
            if not sheet:
                self.log(f"No sheet found for scenario '{scenario}' — skipping")
                continue

            df = xl.parse(sheet, header=None)
            # Stats NZ Excel files have complex headers; try to find year row
            rows = self._parse_stats_nz_sheet(df, scenario, geo_map, conn)
            if not dry_run:
                for row_args in rows:
                    conn.execute("""
                        INSERT INTO fact_demand_projection
                        (id, service_type, geography_id, time_id, scenario,
                         projected_volume, current_capacity, capacity_gap, projection_basis)
                        VALUES (nextval('fact_demand_projection_id_seq'), ?, ?, ?, ?, ?, NULL, NULL, ?)
                    """, row_args)
                    inserted += 1

        self.log(f"Done: {inserted} projection rows inserted")

    def _find_sheet(self, sheet_names, keywords):
        for name in sheet_names:
            name_lower = name.lower()
            if any(kw in name_lower for kw in keywords):
                return name
        return None

    def _parse_stats_nz_sheet(self, df, scenario, geo_map, conn):
        """Parse a Stats NZ projection sheet. Returns list of row tuples.

        NOTE: Excel parsing not implemented — returns empty list.
        The pipeline falls back to demographics_seed.csv automatically.
        To implement, inspect the workbook structure and parse year/region rows.
        """
        self.log("WARNING: Excel parsing not implemented — using seed CSV fallback")
        return []

    def _insert_projections(self, df, conn, dry_run=False):
        """Insert from seed CSV with columns: year, scenario, geography, population."""
        conn.execute("DELETE FROM fact_demand_projection")

        geo_map = {
            (label, stype): gid
            for label, stype, gid in conn.execute(
                "SELECT source_label, source_type, canonical_geography_id FROM geography_map"
            ).fetchall()
        }

        inserted = 0
        skipped = 0

        for _, row in df.iterrows():
            year = row.get("year")
            scenario_raw = str(row.get("scenario", "medium")).strip().lower()
            # Map "medium" → "baseline" to match schema constraint
            scenario = "baseline" if scenario_raw == "medium" else scenario_raw
            geography_label = str(row.get("geography", "New Zealand")).strip()
            population = row.get("population")

            try:
                year_int = int(float(str(year)))
            except (ValueError, TypeError):
                skipped += 1
                continue

            geo_id = (
                geo_map.get((geography_label, "health_region"))
                or geo_map.get((geography_label, "stats_code"))
                or (1 if geography_label.lower() in ("new zealand", "nz", "total") else None)
            )
            if geo_id is None:
                skipped += 1
                continue

            # Ensure time entry
            result = conn.execute(
                "SELECT id FROM dim_time WHERE year = ? AND period_type = 'projection'",
                (year_int,)
            ).fetchone()
            if result:
                time_id = result[0]
            else:
                conn.execute("""
                    INSERT INTO dim_time (id, year, period_label, period_type)
                    VALUES (nextval('dim_time_id_seq'), ?, ?, 'projection')
                """, (year_int, str(year_int)))
                time_id = conn.execute(
                    "SELECT id FROM dim_time WHERE year = ? AND period_type = 'projection'",
                    (year_int,)
                ).fetchone()[0]

            if not dry_run:
                conn.execute("""
                    INSERT INTO fact_demand_projection
                    (id, service_type, geography_id, time_id, scenario,
                     projected_volume, current_capacity, capacity_gap, projection_basis)
                    VALUES (nextval('fact_demand_projection_id_seq'), 'primary', ?, ?, ?, ?, NULL, NULL, ?)
                """, (
                    geo_id, time_id, scenario, float(population) if population else None,
                    "Stats NZ subnational population projection"
                ))
            inserted += 1

        self.log(f"Done: {inserted} projection rows, {skipped} skipped")
