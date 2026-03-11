"""
NZDep2018 transformer.

Reads the Otago SA1-level Excel file, aggregates quintile distributions
and mean scores by health region (via DHB mapping), and inserts into
fact_nzdep.

DHB → health region mapping uses the 2022 Health NZ restructure:
  Northern:     Northland, Waitemata, Auckland, Counties Manukau
  Midland:      Waikato, Lakes, Bay of Plenty, Tairawhiti, Taranaki
  Central:      Hawke's Bay, Whanganui, MidCentral, Capital and Coast,
                Capital & Coast, Hutt Valley, Wairarapa
  South Island: Nelson Marlborough, West Coast, Canterbury,
                South Canterbury, Southern
"""
import pandas as pd
from pathlib import Path
from pipeline.transform.base import BaseTransformer
from pipeline.transform.dhb_regions import DHB_TO_REGION

# Also try national row
NATIONAL_REGION = "National"


class NZDepTransformer(BaseTransformer):
    source_key = "nzdep"

    def transform(self, path: Path, conn, dry_run=False):
        if dry_run:
            self.log("DRY RUN: would aggregate NZDep2018 to health regions")
            return

        conn.execute("DELETE FROM fact_nzdep")

        suffix = path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            df = self._load_excel(path)
        elif suffix == ".csv":
            return self._load_seed_csv(path, conn)
        else:
            self.log(f"Unknown file type {suffix}, skipping")
            return

        if df is None or df.empty:
            self.log("No data loaded, skipping")
            return

        # Resolve health region geography IDs
        geo_rows = conn.execute(
            "SELECT id, name FROM dim_geography WHERE level IN ('national','health_region')"
        ).fetchall()
        geo_map = {name: gid for gid, name in geo_rows}

        national_id = geo_map.get("National") or geo_map.get("New Zealand")

        inserted = 0
        for region_name, group in df.groupby("health_region"):
            geo_id = geo_map.get(region_name)
            if geo_id is None:
                self.log(f"WARNING: no geography_id for region '{region_name}', skipping")
                continue

            scores = group["score"].dropna()
            if scores.empty:
                continue
            quintiles = group["quintile"].dropna()

            total = len(quintiles)
            pct = {q: (quintiles == q).sum() / total * 100 for q in [1, 2, 3, 4, 5]}

            conn.execute("""
                INSERT INTO fact_nzdep
                    (id, geography_id, year, nzdep_mean_score,
                     pct_q1, pct_q2, pct_q3, pct_q4, pct_q5, sa1_count, source)
                VALUES (nextval('fact_nzdep_id_seq'), ?, 2018, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                geo_id,
                float(scores.mean()),
                pct[1], pct[2], pct[3], pct[4], pct[5],
                int(total),
                "NZDep2018 SA1 index — University of Otago",
            ))
            inserted += 1

        # National aggregate
        if national_id and not df.empty:
            scores = df["score"].dropna()
            quintiles = df["quintile"].dropna()
            total = len(quintiles)
            pct = {q: (quintiles == q).sum() / total * 100 for q in [1, 2, 3, 4, 5]}
            conn.execute("""
                INSERT INTO fact_nzdep
                    (id, geography_id, year, nzdep_mean_score,
                     pct_q1, pct_q2, pct_q3, pct_q4, pct_q5, sa1_count, source)
                VALUES (nextval('fact_nzdep_id_seq'), ?, 2018, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                national_id,
                float(scores.mean()),
                pct[1], pct[2], pct[3], pct[4], pct[5],
                int(total),
                "NZDep2018 SA1 index — University of Otago",
            ))
            inserted += 1

        self.log(f"Done: {inserted} NZDep rows inserted")

    def _load_seed_csv(self, path: Path, conn) -> None:
        """Load pre-aggregated seed CSV (geography, year, nzdep_mean_score, pct_q1-5, sa1_count, source)."""
        self.log(f"Loading pre-aggregated NZDep seed CSV: {path}")
        df = pd.read_csv(path)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        geo_rows = conn.execute(
            "SELECT id, name FROM dim_geography WHERE level IN ('national','health_region')"
        ).fetchall()
        geo_map = {name: gid for gid, name in geo_rows}

        inserted = 0
        for _, row in df.iterrows():
            geo_name = str(row.get("geography", "")).strip()
            # Accept "National" or "New Zealand" for national row
            if geo_name.lower() in ("national", "new zealand"):
                geo_id = geo_map.get("National") or geo_map.get("New Zealand")
            else:
                geo_id = geo_map.get(geo_name)
            if geo_id is None:
                self.log(f"WARNING: unknown geography '{geo_name}', skipping")
                continue

            year = int(row.get("year", 2018))
            conn.execute("""
                INSERT INTO fact_nzdep
                    (id, geography_id, year, nzdep_mean_score,
                     pct_q1, pct_q2, pct_q3, pct_q4, pct_q5, sa1_count, source)
                VALUES (nextval('fact_nzdep_id_seq'), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                geo_id, year,
                float(row.get("nzdep_mean_score", 0)),
                float(row.get("pct_q1", 0)),
                float(row.get("pct_q2", 0)),
                float(row.get("pct_q3", 0)),
                float(row.get("pct_q4", 0)),
                float(row.get("pct_q5", 0)),
                int(row.get("sa1_count", 0)),
                str(row.get("source", "NZDep2018 SA1 index — University of Otago")),
            ))
            inserted += 1

        self.log(f"Done: {inserted} NZDep rows inserted from seed CSV")

    def _load_excel(self, path: Path) -> pd.DataFrame | None:
        self.log(f"Loading NZDep2018 Excel: {path} ...")
        try:
            df = pd.read_excel(path, sheet_name=0, engine="openpyxl")
            self.log(f"Loaded {len(df):,} SA1 rows, columns: {list(df.columns)}")
        except Exception as e:
            self.log(f"Failed to read Excel: {e}")
            return None

        # Find score and quintile columns (name varies slightly across releases)
        # Actual column names in the Otago 2018 release:
        #   NZDep2018       → quintile (1-5)
        #   NZDep2018_Score → raw deprivation score
        #   DHB_2018_name   → DHB assignment
        score_col = self._find_col(df, ["NZDep2018_Score", "NZDep2018_score", "NZDep_Score", "score"])
        quintile_col = self._find_col(df, ["NZDep2018", "NZDep2018_quintile", "Quintile", "quintile"])
        dhb_col = self._find_col(df, ["DHB_2018_name", "DHB2018_name", "DHB2015_name", "DHB_name", "DHBName"])

        if score_col is None or dhb_col is None:
            self.log(f"Could not identify required columns. Available: {list(df.columns)}")
            return None

        out = pd.DataFrame()
        out["score"] = pd.to_numeric(df[score_col], errors="coerce")
        out["quintile"] = pd.to_numeric(df[quintile_col], errors="coerce") if quintile_col else None
        out["dhb"] = df[dhb_col].astype(str).str.strip()
        out["health_region"] = out["dhb"].map(DHB_TO_REGION)

        unmatched = out[out["health_region"].isna()]["dhb"].unique()
        if len(unmatched) > 0:
            self.log(f"Unmatched DHB names (will be skipped): {list(unmatched)}")

        out = out[out["health_region"].notna()]

        # If quintile column missing, compute from score
        if quintile_col is None or out["quintile"].isna().all():
            out["quintile"] = pd.qcut(out["score"], 5, labels=[1, 2, 3, 4, 5]).astype(float)

        return out

    @staticmethod
    def _find_col(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        # Case-insensitive fallback
        lower_cols = {col.lower(): col for col in df.columns}
        for c in candidates:
            if c.lower() in lower_cols:
                return lower_cols[c.lower()]
        return None
