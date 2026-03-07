"""
NZ Health Survey transformer.

Handles the actual NZHS Annual Data Explorer prevalence CSV format:
  population, short.description, year, group, total, flag_for_publishing,
  total.low.CI, total.high.CI, male, ...

- Rows where group is an ethnicity → national geography
- Rows where group is a health region → health region geography, Total ethnicity
- Age, deprivation, disability rows → skipped for now
"""
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer

# 'S' = suppressed; 'e' = estimate (publishable, not suppressed)
SUPPRESSION_FLAG = 'S'

# Map short.description values in the NZHS CSV to indicator slugs
# Only indicators that exist in indicator_catalogue.csv are mapped
NZHS_INDICATOR_MAP = {
    # Smoking
    "Current smokers": "current_smoker",
    "Daily smokers": "current_smoker",
    # Obesity
    "Obese": "obesity_adult",          # adults population
    # Drinking
    "Hazardous drinking pattern (total population)": "heavy_drinker",
    # Physical activity
    "Insufficient physical activity": "physical_activity_insufficient",
    "Little or no physical activity": "physical_activity_insufficient",
    # Fruit & veg
    "Meets both vegetable and fruit recommendations": "fruit_veg_adequate",
    "Meets both vegetable and fruit recommendation": "fruit_veg_adequate",
    # Unmet need for GP
    "Unmet need for GP due to cost": "unmet_need_gp",
    # Diabetes
    "Diabetes": "diabetes_diagnosed",
    # Hypertension
    "High blood pressure (medicated)": "hypertension_diagnosed",
    # Mental health
    "Psychological distress - high or very high": "poor_mental_health",
    # Child obesity
    "Overweight or obese": "obesity_child",    # children population
    # Asthma
    "Asthma (using treatment)": "asthma_diagnosed",
}

# Groups in the NZHS CSV that map to ethnicity at national level
ETHNICITY_GROUPS = {"Total", "Māori", "Pacific", "Asian", "European/Other"}

# Groups that map to health regions (use national Total ethnicity)
HEALTH_REGION_GROUPS = {
    "Northern | Te Tai Tokerau",
    "Midland | Te Manawa Taki",
    "Central | Te Ikaroa",
    "South Island | Te Waipounamu",
}


class NZHSTransformer(BaseTransformer):
    source_key = "nzhs_prevalence"

    def transform(self, raw_path: Path, conn, dry_run=False):
        if not raw_path.exists():
            self.log(f"File not found: {raw_path} — skipping")
            return

        self.log(f"Reading {raw_path}")
        df = pd.read_csv(raw_path, encoding="utf-8-sig", low_memory=False)
        self.log(f"Read {len(df)} rows, columns: {list(df.columns)}")

        # Load lookup maps
        eth_map = dict(conn.execute(
            "SELECT source_label, canonical_ethnicity_id FROM ethnicity_map"
        ).fetchall())
        geo_map = {
            (label, stype): gid
            for label, stype, gid in conn.execute(
                "SELECT source_label, source_type, canonical_geography_id FROM geography_map"
            ).fetchall()
        }
        ind_map = dict(conn.execute("SELECT slug, id FROM dim_indicator").fetchall())

        # National geography id
        national_id = conn.execute(
            "SELECT id FROM dim_geography WHERE level = 'national' LIMIT 1"
        ).fetchone()[0]

        # Total ethnicity id
        total_eth_id = eth_map.get("Total")

        # Ensure all years present in dim_time
        time_map = self._ensure_time_entries(conn, df["year"].dropna().unique())

        data_source_id = 1  # NZHS
        inserted = 0
        suppressed_count = 0
        skipped = 0

        for _, row in df.iterrows():
            # Map indicator
            desc = str(row.get("short.description", "")).strip()
            indicator_slug = NZHS_INDICATOR_MAP.get(desc)
            if indicator_slug is None:
                skipped += 1
                continue

            # Only map if indicator exists in catalogue
            indicator_id = ind_map.get(indicator_slug)
            if indicator_id is None:
                skipped += 1
                continue

            population = str(row.get("population", "")).strip()

            # Skip child obesity for adult population (and vice versa)
            if indicator_slug == "obesity_adult" and population == "children":
                skipped += 1
                continue
            if indicator_slug == "obesity_child" and population == "adults":
                skipped += 1
                continue

            group = str(row.get("group", "")).strip()

            # Resolve geography and ethnicity
            if group in ETHNICITY_GROUPS:
                geo_id = national_id
                eth_id = eth_map.get(group)
                if eth_id is None and group != "Total":
                    skipped += 1
                    continue
                if group == "Total":
                    eth_id = total_eth_id
            elif group in HEALTH_REGION_GROUPS:
                geo_id = geo_map.get((group, "nzhs_region"))
                if geo_id is None:
                    self.log(f"WARNING: Unknown health region '{group}' — skipping")
                    skipped += 1
                    continue
                eth_id = total_eth_id
            else:
                # Age groups, deprivation quintiles, disability — skip
                skipped += 1
                continue

            # Year / time
            try:
                year_int = int(float(str(row.get("year", ""))))
            except (ValueError, TypeError):
                skipped += 1
                continue
            time_id = time_map.get(year_int)

            # Value and suppression
            flag = str(row.get("flag_for_publishing", "")).strip()
            is_suppressed = (flag == SUPPRESSION_FLAG)

            raw_val = row.get("total")
            try:
                value = float(raw_val) if not is_suppressed and raw_val is not None and str(raw_val) not in ("", "nan") else None
            except (ValueError, TypeError):
                value = None

            raw_lower = row.get("total.low.CI")
            raw_upper = row.get("total.high.CI")
            try:
                lower_ci = float(raw_lower) if raw_lower is not None and str(raw_lower) not in ("", "nan") else None
                upper_ci = float(raw_upper) if raw_upper is not None and str(raw_upper) not in ("", "nan") else None
            except (ValueError, TypeError):
                lower_ci = upper_ci = None

            if not dry_run:
                conn.execute("""
                    INSERT INTO fact_health_indicator
                    (id, indicator_id, geography_id, ethnicity_id, time_id, data_source_id,
                     value, value_lower_ci, value_upper_ci, suppressed)
                    VALUES (nextval('fact_health_indicator_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    indicator_id, geo_id, eth_id, time_id, data_source_id,
                    value, lower_ci, upper_ci, is_suppressed,
                ))

            inserted += 1
            if is_suppressed:
                suppressed_count += 1

        self.log(
            f"Done: {inserted} rows inserted ({suppressed_count} suppressed, {skipped} skipped)"
        )

    def _ensure_time_entries(self, conn, years) -> dict:
        time_map = dict(conn.execute(
            "SELECT year, id FROM dim_time WHERE period_type = 'annual'"
        ).fetchall())
        for y in years:
            try:
                year_int = int(float(str(y)))
            except (ValueError, TypeError):
                continue
            if year_int not in time_map:
                conn.execute("""
                    INSERT INTO dim_time (id, year, period_label, period_type)
                    VALUES (nextval('dim_time_id_seq'), ?, ?, 'annual')
                """, (year_int, str(year_int)))
                result = conn.execute(
                    "SELECT id FROM dim_time WHERE year = ? AND period_type = 'annual'",
                    (year_int,)
                ).fetchone()
                time_map[year_int] = result[0]
        return time_map
